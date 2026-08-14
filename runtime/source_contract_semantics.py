"""Infer bounded callable contract facts from source evidence."""

from __future__ import annotations

import ast
import textwrap
from typing import Any

from runtime.source_contract_helpers import local_type_factories
from runtime.source_contract_docstrings import documented_output_shape, docstring_argument_types
from runtime.source_dispatch_evidence import has_receiver_request_dispatch, is_receiver_request_dispatch
from runtime.source_effect_evidence import observed_side_effects


_WEAK_TYPES = {
    "", "any", "typing.any", "object", "inferredinput", "inferredoutput", "dispatchedresult",
}


def infer_source_contract(candidate: dict[str, Any]) -> dict[str, Any]:
    precomputed = candidate.get("structural_contract")
    if isinstance(precomputed, dict) and precomputed:
        return {
            **precomputed,
            "decorators": sorted(str(value) for value in candidate.get("decorators", []) if value),
        }
    signature = dict(candidate.get("signature") or {})
    snippet = _snippet_text(candidate.get("snippet"))
    function, source_complete = _function_node(snippet)
    args = [row for row in signature.get("args", []) or [] if isinstance(row, dict)]
    args = [row for row in args if str(row.get("name") or "") not in {"self", "cls"}]
    docstring_types = docstring_argument_types(snippet, [str(row.get("name") or "") for row in args])
    constraint_types = _argument_constraint_types(function, [str(row.get("name") or "") for row in args])
    usage_types = _argument_usage_types(function, [str(row.get("name") or "") for row in args])
    return_annotation = str(signature.get("returns") or "").strip()
    inferred_output, output_basis = _output_shape(function, return_annotation, snippet, source_complete=source_complete)
    typed_args = [row for row in args if _concrete_type(row.get("annotation"))]
    return {
        "source_body_available": function is not None,
        "source_body_complete": source_complete,
        "docstring_available": bool(ast.get_docstring(function)) if function is not None else _has_docstring_prefix(snippet),
        "docstring_argument_types": docstring_types,
        "argument_constraint_types": constraint_types,
        "argument_usage_types": usage_types,
        "argument_count": len(args),
        "typed_argument_count": len(typed_args),
        "explicit_return_annotation": return_annotation,
        "inferred_output_type": inferred_output,
        "output_inference_basis": output_basis,
        "return_paths": _return_path_count(function),
        "raises": _raise_names(function),
        "state_mutation": _has_state_mutation(function),
        "dynamic_dispatch": has_receiver_request_dispatch(function) if function is not None else False,
        "observed_side_effects": observed_side_effects(function, args),
        "decorators": sorted(str(value) for value in candidate.get("decorators", []) if value),
    }


def structural_quality_adjustment(
    evidence: dict[str, Any],
    *,
    input_contract: dict[str, Any] | None = None,
    output_contract: dict[str, Any] | None = None,
    side_effect_contract: dict[str, Any] | None = None,
) -> tuple[int, list[str]]:
    if not evidence:
        return 0, []
    score = 0
    reasons: list[str] = []
    inputs = dict(input_contract or {})
    outputs = dict(output_contract or {})
    effects = dict(side_effect_contract or {})
    concrete_inputs = [value for value in inputs.values() if _concrete_type(value)]
    if inputs and len(concrete_inputs) == len(inputs):
        score += 6
        reasons.append("source-bound input shapes are concrete")
    elif concrete_inputs:
        score += 3
        reasons.append("source-bound input shapes are partially concrete")
    explicit_return = str(evidence.get("explicit_return_annotation") or "").strip()
    inferred_output = str(evidence.get("inferred_output_type") or "").strip()
    if _concrete_type(explicit_return) or explicit_return.lower() in {"none", "nonetype"}:
        score += 8
        reasons.append("return behavior is bound to an explicit annotation")
    elif _concrete_type(inferred_output) and _concrete_output(outputs):
        score += 5
        reasons.append("return shape is inferred from callable body or docstring")
    if evidence.get("source_body_complete"):
        score += 4
        reasons.append("complete callable body is available for structural contract review")
    elif evidence.get("source_body_available"):
        score += 1
        reasons.append("partial callable body provides limited structural evidence")
    if evidence.get("docstring_available"):
        score += 2
        reasons.append("callable docstring corroborates structural evidence")
    if evidence.get("raises") and evidence.get("source_body_complete"):
        score += 4
        reasons.append("explicit failure paths prove a negative contract")
    declared_effects = list(effects.get("declared") or [])
    if declared_effects and effects.get("retry_policy") and effects.get("requires_process_boundary"):
        score += 4
        reasons.append("declared side effects have explicit retry and isolation policy")
    elif "declared" in effects and evidence.get("source_body_complete"):
        score += 2
        reasons.append("complete source analysis found no declared side effects")
    input_types = {str(value) for value in inputs.values()}
    output_types = {str(value) for value in outputs.values()}
    if "RequestLike" in input_types and "ResponseLike" in output_types and evidence.get("source_body_complete"):
        score += 3
        reasons.append("framework request/response boundary is structurally proven")
    void_outputs = {"VoidSideEffect", "VoidPersistenceCommand"}
    mutating_effects = {"memory_state", "database", "filesystem_write", "network"}
    if output_types & void_outputs and set(declared_effects) & mutating_effects and evidence.get("source_body_complete"):
        score += 3
        reasons.append("state transition boundary is structurally proven")
    if not declared_effects and _all_contract_shapes_concrete(inputs, outputs) and evidence.get("source_body_complete"):
        score += 3
        reasons.append("complete source proves a bounded side-effect-free transform")
    return score, reasons


def _output_shape(function: ast.AST | None, annotation: str, snippet: str, *, source_complete: bool) -> tuple[str, str]:
    if annotation:
        has_value_return = function is not None and any(
            isinstance(node, ast.Return) and node.value is not None for node in ast.walk(function)
        )
        if annotation.lower() in {"none", "nonetype"} and not has_value_return:
            return "VoidSideEffect", "explicit_none_annotation"
        if annotation.lower() not in {"any", "typing.any", "object", "none", "nonetype"}:
            return annotation, "explicit_return_annotation"
    if function is not None:
        argument_names = [
            arg.arg
            for arg in [*function.args.posonlyargs, *function.args.args, *function.args.kwonlyargs]
            if arg.arg not in {"self", "cls"}
        ]
        assignments = {
            **_argument_usage_types(function, argument_names),
            **_assignment_shapes(function),
            **local_type_factories(function),
        }
        yielded = [node for node in ast.walk(function) if isinstance(node, (ast.Yield, ast.YieldFrom))]
        if yielded:
            return "IteratorLike", "yield_expression"
        shapes = [_expression_shape(node.value, assignments) for node in ast.walk(function) if isinstance(node, ast.Return) and node.value]
        shapes = [shape for shape in shapes if shape]
        if shapes:
            unique = sorted(set(shapes))
            return (unique[0] if len(unique) == 1 else f"Union[{', '.join(unique)}]"), "return_expression"
        if source_complete and not any(isinstance(node, ast.Return) and node.value for node in ast.walk(function)):
            return "VoidSideEffect", "no_value_return"
    lowered = snippet.lower()
    documented = documented_output_shape(snippet)
    if documented:
        return documented, "docstring_return_contract"
    if "convert" in lowered and ("kwargs" in lowered or "mapping" in lowered or "dictionary" in lowered):
        return "MappingLike", "docstring_semantics"
    return "InferredOutput", "insufficient_structural_evidence"


def _assignment_shapes(function: ast.AST) -> dict[str, str]:
    shapes: dict[str, str] = {}
    for node in ast.walk(function):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            shape = _expression_shape(value, shapes) if value is not None else ""
            for target in targets:
                if isinstance(target, ast.Name) and shape:
                    shapes[target.id] = shape
                elif isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name):
                    shapes[target.value.id] = "MappingLike"
    return shapes


def _expression_shape(node: ast.AST, assignments: dict[str, str]) -> str:
    literals = {ast.Dict: "MappingLike", ast.List: "SequenceLike", ast.ListComp: "SequenceLike", ast.Tuple: "TupleLike", ast.Set: "SetLike"}
    if type(node) in literals:
        return literals[type(node)]
    if isinstance(node, ast.Name):
        if node.id in {"self", "cls"}:
            return "ReceiverState"
        return assignments.get(node.id, "")
    if isinstance(node, ast.Await):
        return _expression_shape(node.value, assignments)
    if isinstance(node, ast.Constant):
        return type(node.value).__name__
    if isinstance(node, ast.Attribute):
        return "AttributeValue"
    if isinstance(node, ast.BinOp):
        return "ArrayLike" if "ArrayLike" in {_expression_shape(value, assignments) for value in (node.left, node.right)} else "NumberLike"
    if isinstance(node, ast.Call):
        if is_receiver_request_dispatch(node):
            return "DispatchedResult"
        name = _call_name(node.func).lower()
        if name == "isinstance":
            return "bool"
        if any(token in name for token in ("render", "request", "response", "redirect")):
            return "ResponseLike"
        if name.endswith(("dict", "to_dict", "kwargs")):
            return "MappingLike"
        owner, _, operation = name.rpartition(".")
        if operation == "get" and any(token in owner.split(".") for token in ("crud", "repo", "repository")):
            return "EntityLike"
        if name.endswith(("list", "all")):
            return "SequenceLike"
        if name.endswith(("numpy", "astype", "tile", "reshape", "transpose", "stack", "concatenate", "hstack", "vstack", "split")) or (name.startswith(("torch.", "np.", "numpy.")) and name.endswith(("sum", "mean", "clamp"))):
            return "ArrayLike"
        if name.endswith(("_item", "from_json")):
            return "ItemLike"
        if name.endswith(("format", "replace", "strip", "zfill")):
            return "str"
        if name.startswith(("np.", "numpy.")) and name.endswith(("exp", "log", "log10", "log2")):
            return "ArrayLike"
        if name.endswith(("image.frombytes", "image.fromarray")):
            return "ImageLike"
        if name.endswith((".execute", ".executemany")):
            return "DatabaseResult"
    return ""
def _function_node(snippet: str) -> tuple[ast.FunctionDef | ast.AsyncFunctionDef | None, bool]:
    if not snippet:
        return None, False
    source = textwrap.dedent(snippet)
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return _partial_function_node(source), False
    return next((node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))), None), True


def _partial_function_node(source: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    lines = source.splitlines()
    for end in range(len(lines), 1, -1):
        candidate = "\n".join(lines[:end]).rstrip() + "\n    pass\n"
        try:
            tree = ast.parse(candidate)
        except SyntaxError:
            continue
        return next((node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))), None)
    return None


def _return_path_count(function: ast.AST | None) -> int:
    return sum(isinstance(node, ast.Return) for node in ast.walk(function)) if function is not None else 0


def _raise_names(function: ast.AST | None) -> list[str]:
    if function is None:
        return []
    return sorted({_call_name(node.exc.func if isinstance(node.exc, ast.Call) else node.exc) for node in ast.walk(function) if isinstance(node, ast.Raise) and node.exc} - {""})


def _has_state_mutation(function: ast.AST | None) -> bool:
    if function is None:
        return False
    local_names = {
        target.id
        for node in ast.walk(function)
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
        if isinstance(target, ast.Name)
    }
    for node in ast.walk(function):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.Delete)):
            if isinstance(node, ast.Delete):
                targets = node.targets
            elif isinstance(node, ast.Assign):
                targets = node.targets
            else:
                targets = [node.target]
            if any(_target_mutates_external_state(target, local_names) for target in targets):
                return True
    return False


def _target_mutates_external_state(target: ast.AST, local_names: set[str]) -> bool:
    if isinstance(target, ast.Attribute):
        return True
    if isinstance(target, ast.Subscript):
        return not isinstance(target.value, ast.Name) or target.value.id not in local_names
    return False


def _call_name(node: ast.AST | None) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def _snippet_text(value: object) -> str:
    return str(value.get("text") or "") if isinstance(value, dict) else str(value or "")


def _has_docstring_prefix(snippet: str) -> bool:
    return '"""' in snippet or "'''" in snippet


def _argument_constraint_types(function: ast.AST | None, names: list[str]) -> dict[str, str]:
    if function is None:
        return {}
    values: dict[str, set[object]] = {name: set() for name in names}
    optional: set[str] = set()
    for node in ast.walk(function):
        if not isinstance(node, ast.Compare) or not isinstance(node.left, ast.Name) or node.left.id not in values:
            continue
        name = node.left.id
        for comparator in node.comparators:
            constants = _constraint_constants(comparator)
            optional.update([name] if None in constants else [])
            values[name].update(value for value in constants if value is not None)
    result = {}
    for name, constants in values.items():
        if not constants:
            continue
        literal = "Literal[" + ", ".join(repr(value) for value in sorted(constants, key=str)) + "]"
        result[name] = f"Optional[{literal}]" if name in optional else literal
    return result


def _argument_usage_types(function: ast.AST | None, names: list[str]) -> dict[str, str]:
    if function is None:
        return {}
    known = set(names)
    inferred: dict[str, str] = {}
    for node in ast.walk(function):
        if isinstance(node, ast.Delete):
            for target in node.targets:
                if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name) and target.value.id in known:
                    inferred[target.value.id] = "MappingLike"
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            name = node.func.value.id
            if node.func.attr in {"execute", "executemany"}:
                for arg in node.args:
                    if isinstance(arg, ast.Name) and arg.id in known:
                        inferred[arg.id] = "SQLLike"
            if name in known and node.func.attr in {"items", "keys", "values", "get", "update", "pop", "setdefault"}:
                inferred[name] = "MappingLike"
            elif name in known and node.func.attr in {"startswith", "endswith", "strip", "split", "zfill", "replace"}:
                inferred[name] = "str"
            elif name in known and node.func.attr in {"astype", "reshape", "transpose", "swapaxes", "tobytes", "numpy"}:
                inferred[name] = "ArrayLike"
            elif name in known:
                inferred.setdefault(name, "ProtocolLike")
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in known and node.attr in {"shape", "dtype", "ndim"}:
            inferred[node.value.id] = "ArrayLike"
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in known:
            inferred.setdefault(node.value.id, "ProtocolLike")
        elif isinstance(node, ast.Call) and _call_name(node.func) == "open":
            for arg in node.args:
                if isinstance(arg, ast.Name) and arg.id in known:
                    inferred[arg.id] = "PathLike"
        elif isinstance(node, ast.Call) and _call_name(node.func) in {"isinstance", "echo_prompt"}:
            for arg in node.args[:1]:
                if isinstance(arg, ast.Name) and arg.id in known:
                    inferred[arg.id] = "ArrayLike" if _call_name(node.func) == "isinstance" else "str"
        elif isinstance(node, (ast.For, ast.comprehension)) and isinstance(node.iter, ast.Name) and node.iter.id in known:
            inferred.setdefault(node.iter.id, "IterableLike")
        elif isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id in known:
            inferred.setdefault(node.value.id, "ArrayLike" if isinstance(node.slice, ast.Tuple) else "IndexableLike")
        elif isinstance(node, ast.BinOp):
            for value in (node.left, node.right):
                if isinstance(value, ast.Name) and value.id in known:
                    inferred.setdefault(value.id, "NumberLike")
        elif isinstance(node, ast.BoolOp):
            for value in node.values:
                if isinstance(value, ast.Name) and value.id in known:
                    inferred.setdefault(value.id, "bool")
        elif isinstance(node, ast.Call) and _call_name(node.func) == "range":
            for arg in node.args:
                if isinstance(arg, ast.Name) and arg.id in known:
                    inferred.setdefault(arg.id, "int")
    return inferred


def _constraint_constants(node: ast.AST) -> set[object]:
    if isinstance(node, ast.Constant):
        return {node.value}
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return {item.value for item in node.elts if isinstance(item, ast.Constant)}
    return set()


def _concrete_output(contract: dict[str, Any]) -> bool:
    return bool(contract) and all(_concrete_type(value) for value in contract.values())


def _all_contract_shapes_concrete(inputs: dict[str, Any], outputs: dict[str, Any]) -> bool:
    return bool(inputs and outputs) and all(_concrete_type(value) for value in [*inputs.values(), *outputs.values()])


def _concrete_type(value: object) -> bool:
    text = str(value or "").strip().lower()
    return bool(text) and text not in _WEAK_TYPES and not text.startswith("inferred")
