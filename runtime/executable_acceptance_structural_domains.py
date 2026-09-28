"""Mapping, membership, format, and import-path structural samples."""

from __future__ import annotations

import ast
import re
from typing import Any

from .executable_acceptance_structural_common import (
    Candidates,
    FunctionNode,
    _direct_parameter,
    _literal,
    _priority,
    _safe_scalar,
    _settings,
)
from .executable_acceptance_structural_shapes import _root_parameter


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
            candidates[name].append((_priority("required_mapping_keys"), {key: [] for key in sorted(required)}, "ast_required_mapping_keys"))


def _literal_membership_domains(node: ast.AST, parameters: set[str], candidates: Candidates) -> None:
    for item in ast.walk(node):
        if not isinstance(item, ast.Compare) or not any(
            isinstance(operator, ast.In) for operator in item.ops
        ):
            continue
        name = _root_parameter(item.left, parameters)
        if not name:
            continue
        for operator, comparator in zip(item.ops, item.comparators):
            if not isinstance(operator, ast.In):
                continue
            values = _literal(comparator)
            if (
                isinstance(values, (list, tuple, set))
                and values
                and all(_safe_scalar(value) for value in values)
            ):
                sample = sorted(values, key=repr)[0]
                candidates[name].append((
                    _priority("allowed_collection_domain"),
                    sample,
                    "ast_literal_membership_domain",
                ))


def _keyword_payload_keys(node: FunctionNode, candidates: Candidates) -> None:
    if node.args.kwarg is None:
        return
    kwargs_name = node.args.kwarg.arg
    for item in ast.walk(node):
        if not isinstance(item, ast.Subscript) or not isinstance(item.value, ast.Name):
            continue
        key = _literal(item.slice)
        if item.value.id == kwargs_name and isinstance(key, str):
            candidates.setdefault(key, []).append((_priority("keyword_payload"), key, "ast_required_keyword_payload"))


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
                candidates[name].append((_priority("validation_format_hint"), sample, "ast_validation_format_hint"))


def _importable_module_paths(
    node: FunctionNode, parameters: set[str], candidates: Candidates
) -> None:
    aliases = _parameter_aliases(node, parameters)
    required_attrs = {
        value
        for item in ast.walk(node)
        if isinstance(item, ast.Call)
        and isinstance(item.func, ast.Name)
        and item.func.id in set(_settings().get("module_attribute_calls") or [])
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
            candidates[name].append((_priority("importable_module_path"), value, "ast_importable_module_path"))


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
        method = str(_settings().get("collection_difference_method") or "")
        if item.func.attr != method or not item.args or not isinstance(item.args[0], ast.Name):
            continue
        receiver = item.func.value
        if not isinstance(receiver, ast.Call) or not receiver.args:
            continue
        name = _direct_parameter(receiver.args[0], parameters)
        allowed = constants.get(item.args[0].id, [])
        if name and allowed:
            candidates[name].append((_priority("allowed_collection_domain"), [allowed[0]], "ast_allowed_collection_domain"))


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
    policy = _settings()
    replacements = dict(policy.get("format_samples") or {})
    for marker, sample in replacements.items():
        if marker in normalized:
            return sample
    match = re.search(str(policy.get("format_pattern") or r"$^"), normalized)
    return match.group(1).lower() if match else ""
