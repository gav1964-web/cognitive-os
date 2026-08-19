"""Infer bounded acceptance samples from local AST constraints."""

from __future__ import annotations

import ast
import re
from datetime import datetime
from typing import Any

Candidates = dict[str, list[tuple[int, Any, str]]]
FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


def collect_structural_samples(
    tree: ast.Module, node: FunctionNode, parameters: set[str], candidates: Candidates
) -> None:
    for item in ast.walk(node):
        _conversion(item, parameters, candidates)
        _strptime(item, parameters, candidates)
        _comparison(item, parameters, candidates)
        _numeric_sequence(item, parameters, candidates)
        _numeric_arithmetic(item, parameters, candidates)
        _length_constraint(item, parameters, candidates)
    _required_mapping_keys(node, parameters, candidates)
    _keyword_payload_keys(node, candidates)
    _validation_format_hints(node, parameters, candidates)
    _parameter_attributes(node, parameters, candidates)
    _importable_module_paths(node, parameters, candidates)
    _allowed_collection_domains(tree, node, parameters, candidates)


def _conversion(node: ast.AST, parameters: set[str], candidates: Candidates) -> None:
    if not isinstance(node, ast.Call) or not node.args or not isinstance(node.func, ast.Name):
        return
    name = _direct_parameter(node.args[0], parameters)
    samples = {"float": "1.0", "int": "1"}
    if name and node.func.id in samples:
        candidates[name].append((80, samples[node.func.id], f"ast_conversion:{node.func.id}"))


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
    candidates[name].append((100, value, "ast_strptime_format"))


def _comparison(node: ast.AST, parameters: set[str], candidates: Candidates) -> None:
    if not isinstance(node, ast.Compare):
        return
    expressions = [node.left, *node.comparators]
    for index, expression in enumerate(expressions):
        name = _direct_parameter(expression, parameters)
        constants = [_literal(item) for offset, item in enumerate(expressions) if offset != index]
        value = next((item for item in constants if _safe_scalar(item)), None)
        if name and value is not None:
            candidates[name].append((70, _comparison_sample(value), "ast_comparison_literal"))


def _numeric_sequence(node: ast.AST, parameters: set[str], candidates: Candidates) -> None:
    if not isinstance(node, ast.Call) or not node.args:
        return
    name = _direct_parameter(node.args[0], parameters)
    called = node.func.attr if isinstance(node.func, ast.Attribute) else ""
    if name and called in {"absolute", "array", "asarray", "flipud"}:
        candidates[name].append((85, [0.0, 1.0], f"ast_numeric_sequence:{called}"))


def _numeric_arithmetic(node: ast.AST, parameters: set[str], candidates: Candidates) -> None:
    if not isinstance(node, ast.BinOp):
        return
    for expression in (node.left, node.right):
        name = _direct_parameter(expression, parameters)
        if name:
            candidates[name].append((92, 1, "ast_numeric_arithmetic"))


def _length_constraint(node: ast.AST, parameters: set[str], candidates: Candidates) -> None:
    if not isinstance(node, ast.Compare):
        return
    expressions = [node.left, *node.comparators]
    for index, expression in enumerate(expressions):
        name = _length_parameter(expression, parameters)
        sizes = [
            _literal(item) for offset, item in enumerate(expressions) if offset != index
        ]
        size = next((value for value in sizes if isinstance(value, int) and 0 <= value <= 32), None)
        if name and size is not None:
            candidates[name].append((88, [0] * size, "ast_length_constraint"))


def _length_parameter(node: ast.AST, parameters: set[str]) -> str:
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
        return ""
    return _direct_parameter(node.args[0], parameters) if node.func.id == "len" and len(node.args) == 1 else ""


def _required_mapping_keys(node: ast.AST, parameters: set[str], candidates: Candidates) -> None:
    keys: dict[str, set[str]] = {name: set() for name in parameters}
    for item in ast.walk(node):
        if not isinstance(item, ast.Subscript) or not isinstance(item.value, ast.Name):
            continue
        key = _literal(item.slice)
        if item.value.id in parameters and isinstance(key, str):
            keys[item.value.id].add(key)
    for name, required in keys.items():
        if required:
            candidates[name].append((90, {key: [] for key in sorted(required)}, "ast_required_mapping_keys"))


def _keyword_payload_keys(node: FunctionNode, candidates: Candidates) -> None:
    if node.args.kwarg is None:
        return
    kwargs_name = node.args.kwarg.arg
    for item in ast.walk(node):
        if not isinstance(item, ast.Subscript) or not isinstance(item.value, ast.Name):
            continue
        key = _literal(item.slice)
        if item.value.id == kwargs_name and isinstance(key, str):
            candidates.setdefault(key, []).append((95, key, "ast_required_keyword_payload"))


def _validation_format_hints(
    node: FunctionNode, parameters: set[str], candidates: Candidates
) -> None:
    for branch in ast.walk(node):
        if not isinstance(branch, ast.If):
            continue
        names = {item.id for item in ast.walk(branch.test) if isinstance(item, ast.Name)} & parameters
        messages = [
            value
            for item in branch.body
            if isinstance(item, ast.Raise) and isinstance(item.exc, ast.Call)
            for arg in item.exc.args[:1]
            for value in [_literal(arg)]
            if isinstance(value, str)
        ]
        sample = next((value for message in messages for value in [_format_hint(message)] if value), "")
        for name in names:
            if sample:
                candidates[name].append((98, sample, "ast_validation_format_hint"))


def _parameter_attributes(node: FunctionNode, parameters: set[str], candidates: Candidates) -> None:
    fields: dict[str, set[str]] = {name: set() for name in parameters}
    called = {
        (item.func.value.id, item.func.attr)
        for item in ast.walk(node)
        if isinstance(item, ast.Call)
        and isinstance(item.func, ast.Attribute)
        and isinstance(item.func.value, ast.Name)
        and item.func.value.id in parameters
    }
    for item in ast.walk(node):
        if isinstance(item, ast.Attribute) and isinstance(item.value, ast.Name):
            key = (item.value.id, item.attr)
            if item.value.id in parameters and key not in called:
                fields[item.value.id].add(item.attr)
    for name, names in fields.items():
        if names:
            candidates[name].append((87, {
                "__fixture__": "declared_model",
                "type": "AcceptanceInput",
                "fields": {field: _attribute_sample(field) for field in sorted(names)},
            }, "ast_parameter_attributes"))


def _attribute_sample(name: str) -> Any:
    if name.startswith(("is_", "has_")) or name in {"nullable", "enabled", "disabled"}:
        return False
    return 0 if name in {"index", "count", "size", "length"} else "sample"


def _importable_module_paths(
    node: FunctionNode, parameters: set[str], candidates: Candidates
) -> None:
    aliases = _parameter_aliases(node, parameters)
    required_attrs = {
        value
        for item in ast.walk(node)
        if isinstance(item, ast.Call)
        and isinstance(item.func, ast.Name)
        and item.func.id in {"getattr", "hasattr"}
        and len(item.args) >= 2
        for value in [_literal(item.args[1])]
        if isinstance(value, str)
    }
    for item in ast.walk(node):
        if not isinstance(item, ast.Call) or len(item.args) < 2:
            continue
        if not isinstance(item.func, ast.Attribute) or item.func.attr != "spec_from_file_location":
            continue
        name = _direct_parameter(item.args[1], parameters)
        if not name and isinstance(item.args[1], ast.Name):
            name = aliases.get(item.args[1].id, "")
        if name:
            value = {"__fixture__": "python_module_path", "fields": {attr: {} for attr in sorted(required_attrs)}}
            candidates[name].append((110, value, "ast_importable_module_path"))


def _parameter_aliases(node: FunctionNode, parameters: set[str]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for item in ast.walk(node):
        if not isinstance(item, (ast.Assign, ast.AnnAssign)):
            continue
        targets = item.targets if isinstance(item, ast.Assign) else [item.target]
        value = item.value
        source = _direct_parameter(value, parameters)
        if not source and isinstance(value, ast.Call) and value.args:
            source = _direct_parameter(value.args[0], parameters)
        for target in targets:
            if source and isinstance(target, ast.Name):
                aliases[target.id] = source
    return aliases


def _allowed_collection_domains(
    tree: ast.Module, node: FunctionNode, parameters: set[str], candidates: Candidates
) -> None:
    constants = _module_literal_collections(tree)
    for item in ast.walk(node):
        if not isinstance(item, ast.Call) or not isinstance(item.func, ast.Attribute):
            continue
        if item.func.attr != "difference" or not item.args or not isinstance(item.args[0], ast.Name):
            continue
        receiver = item.func.value
        if not isinstance(receiver, ast.Call) or not receiver.args:
            continue
        name = _direct_parameter(receiver.args[0], parameters)
        allowed = constants.get(item.args[0].id, [])
        if name and allowed:
            candidates[name].append((105, [allowed[0]], "ast_allowed_collection_domain"))


def _module_literal_collections(tree: ast.Module) -> dict[str, list[Any]]:
    result: dict[str, list[Any]] = {}
    for item in tree.body:
        if not isinstance(item, (ast.Assign, ast.AnnAssign)):
            continue
        targets = item.targets if isinstance(item, ast.Assign) else [item.target]
        value = _literal(item.value)
        if not isinstance(value, (list, tuple, set)) or not value:
            continue
        safe = sorted(value, key=repr)
        if all(_safe_scalar(entry) for entry in safe):
            result.update({target.id: safe for target in targets if isinstance(target, ast.Name)})
    return result


def _format_hint(message: str) -> str:
    normalized = message.upper()
    replacements = {
        "YYYY-MM-DDTHH:MM:SS": "2024-02-03T04:05:06",
        "YYYY-MM-DD": "2024-02-03",
        "YYYY/MM/DD": "2024/02/03",
        "HH:MM:SS": "04:05:06",
    }
    for marker, sample in replacements.items():
        if marker in normalized:
            return sample
    match = re.search(r"FORMAT(?: OF|:)?\s+([A-Z][A-Z0-9_./:-]{2,})", normalized)
    return match.group(1).lower() if match else ""


def _direct_parameter(node: ast.AST, parameters: set[str]) -> str:
    return node.id if isinstance(node, ast.Name) and node.id in parameters else ""


def _literal(node: ast.AST) -> Any:
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return None


def _safe_scalar(value: Any) -> bool:
    return isinstance(value, (str, int, float)) and not isinstance(value, bool)


def _comparison_sample(value: Any) -> Any:
    if isinstance(value, int):
        return max(0, value - 1)
    return value / 2 if isinstance(value, float) else value
