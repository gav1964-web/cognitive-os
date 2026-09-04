"""Source-aware constructor sample inference for exception-pickle replay."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from .exception_pickle_constructor_samples import _sample_constructor_value

def _sample_constructor_value_for_source_file(
    name: str,
    *,
    source_file: Path,
    class_name: str,
    object_contracts: dict[str, Any] | None = None,
) -> Any:
    if _constructor_parameter_uses_string_subscript(source_file, class_name, name):
        return f"sample-{name.lower()}"
    if _constructor_parameter_uses_process_error_attributes(source_file, class_name, name):
        return {
            "__sample__": "called_process_error",
            "returncode": 7,
            "cmd": ["sample-command"],
            "stdout": "sample-stdout",
            "stderr": "sample-stderr",
        }
    if _constructor_parameter_uses_exception_identity(source_file, class_name, name):
        return {"__sample__": "exception", "message": f"sample-{name.lower()}"}
    literal = _constructor_parameter_string_membership_literal(source_file, class_name, name)
    if literal is not None:
        return literal
    if _constructor_parameter_calls_method(source_file, class_name, name, "lower"):
        return f"sample-{name.lower()}"
    if name.lower() == "body" and _constructor_parameter_is_string_rendered(
        source_file,
        class_name,
        name,
    ):
        return "sample-body"
    if object_contracts and name in object_contracts:
        contracted = _sample_constructor_value(name, object_contracts=object_contracts)
        if contracted is not None:
            return contracted
    attribute_sample = _source_backed_attribute_object_sample(source_file, class_name, name)
    if attribute_sample is not None:
        return attribute_sample
    return _sample_constructor_value(name, object_contracts=object_contracts)


def _source_backed_attribute_object_sample(
    source_file: Path,
    class_name: str,
    parameter: str,
) -> dict[str, Any] | None:
    attributes = sorted(_constructor_parameter_attribute_names(source_file, class_name, parameter))
    chains = _constructor_parameter_attribute_chains(source_file, class_name, parameter)
    if not attributes and not chains:
        return None
    if len(attributes) + len(chains) > 6:
        return None
    if any(name.startswith("_") for name in attributes):
        return None
    payload: dict[str, Any] = {"__sample__": "named_object"}
    lowered = parameter.lower()
    for attr in attributes:
        if attr in {"content", "name", "tool_name", "value"}:
            payload[attr] = f"sample-{lowered}-{attr}"
        elif attr in {"status_code", "code", "errno", "returncode"}:
            payload[attr] = 7
        else:
            payload[attr] = f"sample-{lowered}-{attr}"
    for chain in chains:
        if any(part.startswith("_") for part in chain) or len(chain) != 2:
            return None
        first, second = chain
        nested = payload.get(first)
        if not isinstance(nested, dict) or nested.get("__sample__") != "named_object":
            nested = {"__sample__": "named_object", "name": f"sample-{lowered}-{first}"}
        nested[second] = _sample_attribute_value(lowered, second)
        payload[first] = nested
    if "name" not in payload:
        payload["name"] = f"sample-{lowered}"
    return payload


def _sample_attribute_value(parameter: str, attribute: str) -> Any:
    if attribute in {"status_code", "code", "errno", "returncode", "port"}:
        return 7
    if attribute.startswith("ERROR_URI") or attribute.endswith("URI"):
        return "https://example.invalid/errors/"
    if attribute in {"ssl"}:
        return True
    return f"sample-{parameter}-{attribute.lower()}"


def _constructor_sample_call(
    *,
    source_file: Path,
    class_name: str,
    required: list[str],
    samples: list[Any],
) -> tuple[list[Any], dict[str, Any]]:
    if not source_file.is_file() or not class_name.isidentifier():
        return samples, {}
    try:
        source = source_file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        source = source_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return samples, {}
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return samples, {}
    init_node = _constructor_init_node(tree, class_name)
    if init_node is None:
        return samples, {}
    positional = [node.arg for node in [*init_node.args.posonlyargs, *init_node.args.args]][1:]
    keyword_only = {node.arg for node in init_node.args.kwonlyargs}
    by_name = dict(zip(required, samples))
    args = [by_name[name] for name in required if name in positional]
    kwargs = {name: by_name[name] for name in required if name in keyword_only}
    if len(args) + len(kwargs) != len(required):
        return samples, {}
    return args, kwargs


def _constructor_parameter_uses_string_subscript(
    source_file: Path,
    class_name: str,
    parameter: str,
) -> bool:
    if not source_file.is_file() or not class_name.isidentifier() or not parameter.isidentifier():
        return False
    if _obviously_numeric_parameter(parameter):
        return False
    try:
        source = source_file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        source = source_file.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    init_node = _constructor_init_node(tree, class_name)
    if init_node is None:
        return False
    for node in ast.walk(init_node):
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id == parameter
            and _subscript_slice_is_string_like(node.slice)
        ):
            return True
    return False


def _constructor_parameter_uses_process_error_attributes(
    source_file: Path,
    class_name: str,
    parameter: str,
) -> bool:
    if not source_file.is_file() or not class_name.isidentifier() or not parameter.isidentifier():
        return False
    if parameter.lower() not in {"error", "cause", "original", "original_error", "exception"}:
        return False
    attributes = _constructor_parameter_attribute_names(source_file, class_name, parameter)
    return bool(attributes & {"stderr", "stdout", "returncode", "cmd", "output"})


def _constructor_parameter_uses_exception_identity(
    source_file: Path,
    class_name: str,
    parameter: str,
) -> bool:
    if not source_file.is_file() or not class_name.isidentifier() or not parameter.isidentifier():
        return False
    init_node = _read_constructor_init(source_file, class_name, parameter)
    if init_node is None:
        return False
    for node in ast.walk(init_node):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == parameter
            and node.attr == "__class__"
        ):
            return True
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Name):
            continue
        if node.value.id != parameter:
            continue
        for target in node.targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
                and target.attr in {"original", "cause", "__cause__"}
            ):
                return True
    return False


def _constructor_parameter_string_membership_literal(
    source_file: Path,
    class_name: str,
    parameter: str,
) -> str | None:
    init_node = _read_constructor_init(source_file, class_name, parameter)
    if init_node is None:
        return None
    for node in ast.walk(init_node):
        if not isinstance(node, ast.Compare) or not isinstance(node.left, ast.Name) or node.left.id != parameter:
            continue
        for operator, comparator in zip(node.ops, node.comparators):
            if not isinstance(operator, (ast.In, ast.NotIn)):
                continue
            values = comparator.elts if isinstance(comparator, (ast.Set, ast.Tuple, ast.List)) else []
            for value in values:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    return value.value
    return None


def _constructor_parameter_calls_method(
    source_file: Path,
    class_name: str,
    parameter: str,
    method: str,
) -> bool:
    init_node = _read_constructor_init(source_file, class_name, parameter)
    if init_node is None or not method.isidentifier():
        return False
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == method
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == parameter
        for node in ast.walk(init_node)
    )


def _read_constructor_init(
    source_file: Path,
    class_name: str,
    parameter: str,
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    if not source_file.is_file() or not class_name.isidentifier() or not parameter.isidentifier():
        return None
    try:
        source = source_file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        source = source_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    return _constructor_init_node(tree, class_name)


def _constructor_parameter_attribute_names(
    source_file: Path,
    class_name: str,
    parameter: str,
) -> set[str]:
    try:
        source = source_file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        source = source_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    init_node = _constructor_init_node(tree, class_name)
    if init_node is None:
        return set()
    return {
        node.attr
        for node in ast.walk(init_node)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == parameter
        and node.attr.isidentifier()
    }


def _constructor_parameter_attribute_chains(
    source_file: Path,
    class_name: str,
    parameter: str,
) -> set[tuple[str, str]]:
    init_node = _read_constructor_init(source_file, class_name, parameter)
    if init_node is None:
        return set()
    chains: set[tuple[str, str]] = set()
    for node in ast.walk(init_node):
        if not (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Attribute)
            and isinstance(node.value.value, ast.Name)
            and node.value.value.id == parameter
            and node.value.attr.isidentifier()
            and node.attr.isidentifier()
        ):
            continue
        chains.add((node.value.attr, node.attr))
    return chains


def _constructor_parameter_is_string_rendered(
    source_file: Path,
    class_name: str,
    parameter: str,
) -> bool:
    if not source_file.is_file() or not class_name.isidentifier() or not parameter.isidentifier():
        return False
    try:
        source = source_file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        source = source_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    init_node = _constructor_init_node(tree, class_name)
    if init_node is None:
        return False
    for node in ast.walk(init_node):
        if isinstance(node, ast.FormattedValue) and _node_mentions_name(node.value, parameter):
            return True
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "str"
            and any(_node_mentions_name(arg, parameter) for arg in node.args)
        ):
            return True
    return False


def _node_mentions_name(node: ast.AST, name: str) -> bool:
    return any(isinstance(child, ast.Name) and child.id == name for child in ast.walk(node))


def _constructor_init_node(tree: ast.AST, class_name: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    for node in getattr(tree, "body", []):
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == "__init__":
                return item
    return None


def _subscript_slice_is_string_like(slice_node: ast.AST) -> bool:
    if isinstance(slice_node, ast.Slice):
        return True
    if isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, int):
        return True
    return False


def _obviously_numeric_parameter(name: str) -> bool:
    lowered = name.lower()
    return lowered in {
        "lineno",
        "line_no",
        "line_number",
        "column",
        "columnno",
        "colno",
        "port",
        "status_code",
        "exit_code",
        "returncode",
        "return_code",
        "retry_count",
        "timeout_seconds",
        "step_index",
        "maximum",
        "minimum",
        "limit",
        "count",
        "total",
        "size",
        "amount",
        "number",
    }
