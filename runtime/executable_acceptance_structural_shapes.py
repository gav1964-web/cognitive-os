"""Shape-driven structural samples for executable acceptance."""

from __future__ import annotations

import ast
from datetime import datetime
from typing import Any

from .executable_acceptance_arithmetic_samples import add_numeric_arithmetic_sample
from .executable_acceptance_structural_common import (
    Candidates,
    FunctionNode,
    _comparison_sample,
    _direct_parameter,
    _literal,
    _priority,
    _safe_scalar,
    _settings,
)
from .source_expression_shapes import assignment_shapes


def _tensor_window_contract_samples(
    node: FunctionNode, parameters: set[str], candidates: Candidates
) -> None:
    policy = dict(_settings().get("tensor_window_contract") or {})
    if not policy.get("enabled"):
        return
    tensor_parameters = {
        argument.arg
        for argument in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
        if argument.arg in parameters
        and argument.annotation is not None
        and "tensor" in ast.unparse(argument.annotation).lower()
    }
    viewed_tensors = {
        name
        for item in ast.walk(node)
        if isinstance(item, ast.Call)
        and isinstance(item.func, ast.Attribute)
        and item.func.attr == "view"
        for name in [_root_parameter(item.func.value, parameters)]
        if name in tensor_parameters
    }
    tuple_parameters = {
        name
        for item in ast.walk(node)
        if isinstance(item, (ast.Assign, ast.AnnAssign))
        for target in (item.targets if isinstance(item, ast.Assign) else [item.target])
        for name in [_direct_parameter(item.value, parameters)]
        if name and _unpack_count(target) == 2
    }
    divided_parameters = {
        name
        for item in ast.walk(node)
        if isinstance(item, ast.BinOp) and isinstance(item.op, ast.FloorDiv)
        for name in (part.id for part in ast.walk(item) if isinstance(part, ast.Name))
        if name in parameters
    }
    if len(viewed_tensors) != 1 or len(tuple_parameters) < 2 or not divided_parameters:
        return
    dimension = int(policy.get("dimension") or 2)
    if dimension < 1 or dimension > int(_settings().get("maximum_inferred_length") or 32):
        return
    priority = _priority("tensor_window_contract")
    for name in viewed_tensors:
        candidates[name].append((
            priority,
            {"__fixture__": "torch_tensor_zeros", "shape": [1, dimension, dimension, 1]},
            "ast_tensor_window_contract",
        ))
    for name in tuple_parameters:
        candidates[name].append((priority, [dimension, dimension], "ast_tensor_window_contract"))
    for name in divided_parameters:
        candidates[name].append((priority, dimension, "ast_tensor_window_contract"))


def _array_axis_samples(node: FunctionNode, parameters: set[str], candidates: Candidates) -> None:
    axes: dict[str, int] = {}
    methods = {"amax", "amin", "argmax", "argmin", "mean", "std", "sum"}
    for item in ast.walk(node):
        if not isinstance(item, ast.Call) or not isinstance(item.func, ast.Attribute):
            continue
        if item.func.attr not in methods:
            continue
        axis_node = item.args[0] if item.args else next(
            (keyword.value for keyword in item.keywords if keyword.arg == "axis"), None
        )
        axis = _literal(axis_node) if axis_node is not None else None
        if not isinstance(axis, int) or axis < 0 or axis > 4:
            continue
        used = {part.id for part in ast.walk(item.func.value) if isinstance(part, ast.Name)} & parameters
        for name in used:
            axes[name] = max(axis, axes.get(name, -1))
    for name, axis in axes.items():
        candidates[name].append((
            _priority("array_axis"),
            {"__fixture__": "numpy_array", "items": _positive_cube(axis + 1)},
            f"ast_array_axis:{axis}",
        ))


def _positive_cube(dimensions: int) -> Any:
    value: Any = [0.4, 0.6]
    for _ in range(max(0, dimensions - 1)):
        value = [value, value]
    return value


def _dynamic_type_checks(node: FunctionNode, parameters: set[str], candidates: Candidates) -> None:
    for item in ast.walk(node):
        if not isinstance(item, ast.Call) or not isinstance(item.func, ast.Name):
            continue
        if item.func.id != "isinstance" or len(item.args) < 2:
            continue
        value_name = _direct_parameter(item.args[0], parameters)
        type_name = _direct_parameter(item.args[1], parameters)
        if value_name and type_name:
            candidates[value_name].append((
                _priority("dynamic_type_check"),
                _settings()["dynamic_type_check_sample"],
                f"ast_dynamic_type_check:{type_name}",
            ))


def _conversion(node: ast.AST, parameters: set[str], candidates: Candidates) -> None:
    if not isinstance(node, ast.Call) or not node.args or not isinstance(node.func, ast.Name):
        return
    name = _direct_parameter(node.args[0], parameters)
    samples = dict(_settings().get("conversion_samples") or {})
    if name and node.func.id in samples:
        candidates[name].append((_priority("conversion"), samples[node.func.id], f"ast_conversion:{node.func.id}"))


def _strptime(node: ast.AST, parameters: set[str], candidates: Candidates) -> None:
    if not isinstance(node, ast.Call) or len(node.args) < 2:
        return
    if not isinstance(node.func, ast.Attribute) or node.func.attr != "strptime":
        return
    name = _direct_parameter(node.args[0], parameters)
    format_value = _literal(node.args[1])
    if not name or not isinstance(format_value, str):
        return
    try:
        value = datetime(2024, 2, 3, 4, 5, 6).strftime(format_value)
    except (TypeError, ValueError):
        return
    candidates[name].append((_priority("strptime_format"), value, "ast_strptime_format"))


def _comparison(node: ast.AST, parameters: set[str], candidates: Candidates) -> None:
    if not isinstance(node, ast.Compare):
        return
    expressions = [node.left, *node.comparators]
    for index, expression in enumerate(expressions):
        name = _direct_parameter(expression, parameters)
        constants = [_literal(item) for offset, item in enumerate(expressions) if offset != index]
        value = next((item for item in constants if _safe_scalar(item)), None)
        if name and value is not None:
            candidates[name].append((_priority("comparison_literal"), _comparison_sample(value), "ast_comparison_literal"))


def _numeric_sequence(node: ast.AST, parameters: set[str], candidates: Candidates) -> None:
    if not isinstance(node, ast.Call) or not node.args:
        return
    name = _direct_parameter(node.args[0], parameters)
    called = node.func.attr if isinstance(node.func, ast.Attribute) else ""
    policy = _settings()
    if name and called in set(policy.get("numeric_sequence_calls") or []):
        candidates[name].append((_priority("numeric_sequence"), policy["numeric_sequence_sample"], f"ast_numeric_sequence:{called}"))


def _length_constraint(
    node: ast.AST, parameters: set[str], candidates: Candidates, string_sequences: set[str]
) -> None:
    if not isinstance(node, ast.Compare):
        return
    expressions = [node.left, *node.comparators]
    for index, expression in enumerate(expressions):
        name = _length_parameter(expression, parameters)
        sizes = [
            _literal(item) for offset, item in enumerate(expressions) if offset != index
        ]
        maximum = int(_settings().get("maximum_inferred_length") or 0)
        size = next((value for value in sizes if isinstance(value, int) and 0 <= value <= maximum), None)
        if name and size is not None:
            samples = dict(_settings().get("length_constraint_samples") or {})
            element = samples.get("string_element") if name in string_sequences else samples.get("default_element")
            value = str(element) * size if name in string_sequences else [element] * size
            candidates[name].append((_priority("length_constraint"), value, "ast_length_constraint"))


def _string_sequence_parameters(node: FunctionNode, parameters: set[str]) -> set[str]:
    result: set[str] = set()
    for item in ast.walk(node):
        if not isinstance(item, ast.Compare):
            continue
        expressions = [item.left, *item.comparators]
        if not any(isinstance(_literal(expression), str) for expression in expressions):
            continue
        for expression in expressions:
            value = expression.value if isinstance(expression, ast.Subscript) else expression
            name = _direct_parameter(value, parameters)
            if name:
                result.add(name)
    return result


def _length_parameter(node: ast.AST, parameters: set[str]) -> str:
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
        return ""
    return _direct_parameter(node.args[0], parameters) if node.func.id == "len" and len(node.args) == 1 else ""


def _root_parameter(node: ast.AST, parameters: set[str]) -> str:
    if name := _direct_parameter(node, parameters):
        return name
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        return _root_parameter(node.func.value, parameters)
    return ""


def _unpack_count(node: ast.AST) -> int:
    return len(node.elts) if isinstance(node, (ast.Tuple, ast.List)) else 0



def add_shape_structural_samples(
    node: FunctionNode, parameters: set[str], candidates: Candidates
) -> set[str]:
    string_sequences = _string_sequence_parameters(node, parameters)
    assignments = assignment_shapes(node)
    _array_axis_samples(node, parameters, candidates)
    _tensor_window_contract_samples(node, parameters, candidates)
    for item in ast.walk(node):
        _conversion(item, parameters, candidates)
        _strptime(item, parameters, candidates)
        _comparison(item, parameters, candidates)
        _numeric_sequence(item, parameters, candidates)
        add_numeric_arithmetic_sample(
            item,
            parameters,
            candidates,
            assignments,
            priority=_priority("numeric_arithmetic"),
            sample=_settings()["numeric_arithmetic_sample"],
        )
        _length_constraint(item, parameters, candidates, string_sequences)
    return string_sequences
