"""Argument-level semantic inference for source contract analysis."""

from __future__ import annotations

import ast

from runtime.source_ast_scope import callable_scope_walk
from runtime.source_contract_argument_types import qualified_call_argument_types
from runtime.source_expression_shapes import assignment_shapes, expression_shape


def argument_constraint_types(function: ast.AST | None, names: list[str]) -> dict[str, str]:
    if function is None:
        return {}
    values: dict[str, set[object]] = {name: set() for name in names}
    optional: set[str] = set()
    for node in callable_scope_walk(function):
        if not isinstance(node, ast.Compare) or not isinstance(node.left, ast.Name) or node.left.id not in values:
            continue
        name = node.left.id
        for comparator in node.comparators:
            constants = constraint_constants(comparator)
            optional.update([name] if None in constants else [])
            values[name].update(value for value in constants if value is not None)
    result = {}
    for name, constants in values.items():
        if not constants:
            continue
        literal = "Literal[" + ", ".join(repr(value) for value in sorted(constants, key=str)) + "]"
        result[name] = f"Optional[{literal}]" if name in optional else literal
    return result


def argument_default_types(function: ast.AST | None, names: list[str]) -> dict[str, str]:
    if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return {}
    positional = [arg for arg in [*function.args.posonlyargs, *function.args.args] if arg.arg in names]
    rows = list(zip(positional[-len(function.args.defaults):], function.args.defaults)) if function.args.defaults else []
    rows.extend(
        (arg, default) for arg, default in zip(function.args.kwonlyargs, function.args.kw_defaults)
        if arg.arg in names and default is not None
    )
    result = {}
    for arg, default in rows:
        if isinstance(default, ast.Constant):
            result[arg.arg] = type(default.value).__name__
        elif isinstance(default, (ast.List, ast.Tuple, ast.Dict, ast.Set)):
            result[arg.arg] = {ast.List: "SequenceLike", ast.Tuple: "TupleLike", ast.Dict: "MappingLike", ast.Set: "SetLike"}[type(default)]
    return result


def argument_usage_types(function: ast.AST | None, names: list[str]) -> dict[str, str]:
    if function is None:
        return {}
    known = set(names)
    inferred = qualified_call_argument_types(function, known)
    assignments = assignment_shapes(function)
    numerical_context = any(
        isinstance(node, ast.Call) and call_name(node.func).lower().startswith(("np.", "numpy.", "torch.", "tf.", "tensorflow."))
        for node in callable_scope_walk(function)
    )
    for node in callable_scope_walk(function):
        _update_usage_from_node(node, inferred, known, assignments, numerical_context)
    return inferred


def _update_usage_from_node(
    node: ast.AST,
    inferred: dict[str, str],
    known: set[str],
    assignments: dict[str, str],
    numerical_context: bool,
) -> None:
    if isinstance(node, ast.Delete):
        for target in node.targets:
            if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name) and target.value.id in known:
                inferred[target.value.id] = "MappingLike"
    elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
        _update_attribute_call_usage(node, inferred, known, numerical_context)
    elif isinstance(node, ast.Call) and call_name(node.func).lower().startswith(("np.", "numpy.", "torch.", "tf.", "tensorflow.")):
        for arg_name in argument_names(node.args, known):
            inferred[arg_name] = "ArrayLike"
    elif isinstance(node, ast.Call) and call_name(node.func).lower().endswith((".verify", ".verify_password", ".check_password", ".hash")):
        for arg_name in argument_names(node.args, known):
            inferred[arg_name] = "str"
    elif isinstance(node, ast.FormattedValue) and isinstance(node.value, ast.Name) and node.value.id in known:
        inferred[node.value.id] = "str"
    elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in known and node.attr in {"shape", "dtype", "ndim"}:
        inferred[node.value.id] = "ArrayLike"
    elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in known:
        inferred.setdefault(node.value.id, "ProtocolLike")
    elif isinstance(node, (ast.Assign, ast.AnnAssign)):
        _update_assignment_usage(node, inferred, known, numerical_context)
    elif isinstance(node, ast.Call) and call_name(node.func) == "open":
        for arg in node.args:
            if isinstance(arg, ast.Name) and arg.id in known:
                inferred[arg.id] = "PathLike"
    elif isinstance(node, ast.Call) and call_name(node.func) in {"isinstance", "echo_prompt"}:
        for arg in node.args[:1]:
            if isinstance(arg, ast.Name) and arg.id in known:
                inferred[arg.id] = isinstance_type(node) if call_name(node.func) == "isinstance" else "str"
    elif isinstance(node, (ast.For, ast.comprehension)) and isinstance(node.iter, ast.Name) and node.iter.id in known:
        inferred.setdefault(node.iter.id, "IterableLike")
    elif isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Name) and node.slice.id in known:
        inferred.setdefault(node.slice.id, "KeyLike")
    elif isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id in known:
        inferred.setdefault(node.value.id, "ArrayLike" if isinstance(node.slice, ast.Tuple) else "IndexableLike")
    elif isinstance(node, ast.BinOp):
        _update_binop_usage(node, inferred, known, assignments)
    elif isinstance(node, ast.BoolOp):
        if all(isinstance(value, ast.Name) for value in node.values):
            for value in node.values:
                if value.id in known:
                    inferred.setdefault(value.id, "bool")
    elif isinstance(node, ast.Compare):
        for value in (node.left, *node.comparators):
            if isinstance(value, ast.Name) and value.id in known:
                inferred.setdefault(value.id, "ScalarLike")
    elif isinstance(node, ast.Call) and call_name(node.func) in {"len", "range"}:
        for arg in node.args:
            for name in argument_names([arg], known):
                inferred.setdefault(name, "SequenceLike" if call_name(node.func) == "len" else "int")


def _update_attribute_call_usage(node: ast.Call, inferred: dict[str, str], known: set[str], numerical_context: bool) -> None:
    name = node.func.value.id
    call = call_name(node.func).lower()
    if (name == "self" and numerical_context) or call.startswith(("np.", "numpy.", "torch.", "tf.", "tensorflow.")):
        for arg_name in argument_names(node.args, known):
            inferred[arg_name] = "ArrayLike"
    if node.func.attr in {"execute", "executemany"}:
        for arg in node.args:
            if isinstance(arg, ast.Name) and arg.id in known:
                inferred[arg.id] = "SQLLike"
    if node.func.attr in {"verify", "verify_password", "check_password", "hash"}:
        for arg_name in argument_names(node.args, known):
            inferred[arg_name] = "str"
    if name in known and node.func.attr in {"items", "keys", "values", "get", "update", "pop", "setdefault"}:
        inferred[name] = "MappingLike"
    elif name in known and node.func.attr in {"startswith", "endswith", "strip", "split", "zfill", "replace"}:
        inferred[name] = "str"
    elif name in known and node.func.attr in {"astype", "contiguous", "dim", "mean", "reshape", "sum", "transpose", "swapaxes", "tobytes", "numpy"}:
        inferred[name] = "ArrayLike"
    elif name in known:
        inferred.setdefault(name, "ProtocolLike")


def _update_assignment_usage(node: ast.Assign | ast.AnnAssign, inferred: dict[str, str], known: set[str], numerical_context: bool) -> None:
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    if isinstance(node.value, ast.Name) and node.value.id in known and any(isinstance(target, (ast.Tuple, ast.List)) for target in targets):
        inferred[node.value.id] = "ArrayLike" if numerical_context else "SequenceLike"


def _update_binop_usage(node: ast.BinOp, inferred: dict[str, str], known: set[str], assignments: dict[str, str]) -> None:
    if isinstance(node.op, ast.Mod) and isinstance(node.left, ast.Constant) and isinstance(node.left.value, str):
        for name in format_argument_names(node.right, known):
            inferred.setdefault(name, "ScalarLike")
    result_shape = expression_shape(node, assignments)
    for value in (node.left, node.right):
        if isinstance(value, ast.Name) and value.id in known:
            inferred[value.id] = "str" if result_shape == "str" else inferred.get(value.id, "NumberLike")


def call_name(node: ast.AST | None) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def format_argument_names(node: ast.AST, known: set[str]) -> set[str]:
    return {child.id for child in ast.walk(node) if isinstance(child, ast.Name) and child.id in known}


def argument_names(nodes: list[ast.AST], known: set[str]) -> set[str]:
    return {child.id for node in nodes for child in ast.walk(node) if isinstance(child, ast.Name) and child.id in known}


def isinstance_type(node: ast.Call) -> str:
    if len(node.args) < 2:
        return "ProtocolLike"
    declared = call_name(node.args[1]).rsplit(".", 1)[-1]
    return declared if declared in {"bool", "bytes", "dict", "float", "int", "list", "str", "tuple"} else "ProtocolLike"


def constraint_constants(node: ast.AST) -> set[object]:
    if isinstance(node, ast.Constant):
        return {node.value}
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return {item.value for item in node.elts if isinstance(item, ast.Constant)}
    return set()
