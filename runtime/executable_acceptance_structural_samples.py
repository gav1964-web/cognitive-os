"""Infer bounded acceptance samples from local AST constraints."""

from __future__ import annotations

import ast
import re
from datetime import datetime
from typing import Any

from .executable_acceptance_attribute_samples import add_parameter_attribute_samples
from .executable_acceptance_file_samples import add_delimited_file_samples
from .executable_acceptance_literal_buffers import add_literal_buffer_samples
from .executable_acceptance_policy import structural_sample_policy
from .executable_acceptance_parameter_strategies import add_parameter_strategy_samples
from .executable_acceptance_protocol_samples import add_iterated_literal_domain_samples, add_mapping_protocol_samples, add_parameter_method_samples
from .executable_acceptance_qualified_samples import add_qualified_call_samples

Candidates = dict[str, list[tuple[int, Any, str]]]
FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef
def _settings() -> dict[str, Any]:
    return structural_sample_policy()


def _priority(name: str) -> int:
    return int(dict(_settings().get("priorities") or {})[name])
def collect_structural_samples(
    tree: ast.Module, node: FunctionNode, parameters: set[str], candidates: Candidates
) -> None:
    add_iterated_literal_domain_samples(node, parameters, candidates, priority=_priority("iterated_literal_domain"))
    buffer_policy = dict(_settings().get("literal_buffer_methods") or {})
    add_literal_buffer_samples(
        node,
        parameters,
        candidates,
        priority=_priority("literal_buffer_method"),
        methods=dict(buffer_policy.get("positions") or {}),
        minimum_length=min(
            int(buffer_policy.get("minimum_length") or 0),
            int(_settings().get("maximum_inferred_length") or 0),
        ),
    )
    add_qualified_call_samples(
        node, parameters, candidates,
        priority=_priority("qualified_call_argument"),
        samples=dict(_settings().get("qualified_call_argument_samples") or {}),
    )
    string_sequences = _string_sequence_parameters(node, parameters)
    for item in ast.walk(node):
        _conversion(item, parameters, candidates)
        _strptime(item, parameters, candidates)
        _comparison(item, parameters, candidates)
        _numeric_sequence(item, parameters, candidates)
        _numeric_arithmetic(item, parameters, candidates)
        _length_constraint(item, parameters, candidates, string_sequences)
    _required_mapping_keys(node, parameters, candidates)
    _parameter_unpack_samples(node, parameters, candidates)
    add_parameter_strategy_samples(node, parameters, candidates,
        policy=dict(_settings().get("parameter_strategies") or {}), priorities=dict(_settings().get("priorities") or {}))
    _parameter_callable_samples(node, parameters, candidates)
    _split_unpack_samples(node, parameters, candidates)
    _keyword_payload_keys(node, candidates)
    _validation_format_hints(node, parameters, candidates)
    add_parameter_attribute_samples(
        tree, node, parameters, candidates,
        priority=_priority("parameter_attributes"),
        attribute_policy=dict(_settings().get("attribute_samples") or {}),
    )
    add_parameter_method_samples(
        node, parameters, candidates,
        priority=_priority("parameter_attributes"),
        prefixes=tuple(str(item) for item in _settings().get("protocol_method_prefixes", [])),
    )
    add_mapping_protocol_samples(
        node, parameters, candidates,
        priority=_priority("parameter_attributes"),
        methods={str(item) for item in _settings().get("mapping_protocol_methods", [])},
        sample=dict(_settings().get("mapping_protocol_sample") or {}),
    )
    add_delimited_file_samples(
        node, parameters, candidates, priority=_priority("importable_module_path")
    )
    _importable_module_paths(node, parameters, candidates)
    _allowed_collection_domains(tree, node, parameters, candidates)


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


def _numeric_arithmetic(node: ast.AST, parameters: set[str], candidates: Candidates) -> None:
    if not isinstance(node, ast.BinOp):
        return
    if isinstance(node.op, ast.Mod) and any(isinstance(_literal(value), str) for value in (node.left, node.right)):
        return
    for expression in (node.left, node.right):
        name = _direct_parameter(expression, parameters)
        if name:
            candidates[name].append((_priority("numeric_arithmetic"), _settings()["numeric_arithmetic_sample"], "ast_numeric_arithmetic"))


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


def _parameter_unpack_samples(node: FunctionNode, parameters: set[str], candidates: Candidates) -> None:
    policy = dict(_settings().get("unpack_samples") or {})
    maximum = int(policy.get("maximum_items") or 0)
    for item in ast.walk(node):
        if not isinstance(item, (ast.Assign, ast.AnnAssign)):
            continue
        targets = item.targets if isinstance(item, ast.Assign) else [item.target]
        name = _direct_parameter(item.value, parameters)
        count = max((_unpack_count(target) for target in targets), default=0)
        if name and 1 < count <= maximum:
            sample = [policy.get("element")] * count
            candidates[name].append((_priority("parameter_unpack"), sample, "ast_parameter_unpack"))


def _parameter_callable_samples(
    node: FunctionNode, parameters: set[str], candidates: Candidates
) -> None:
    fixture = str(_settings().get("parameter_callable_fixture") or "")
    if not fixture:
        return
    for item in ast.walk(node):
        if not isinstance(item, ast.Call):
            continue
        name = _direct_parameter(item.func, parameters)
        if name:
            candidates[name].append(
                (_priority("parameter_callable"), {"__fixture__": fixture}, "ast_parameter_callable")
            )


def _split_unpack_samples(node: FunctionNode, parameters: set[str], candidates: Candidates) -> None:
    policy = dict(_settings().get("unpack_samples") or {})
    methods = set(policy.get("split_methods") or [])
    maximum = int(policy.get("maximum_items") or 0)
    for item in ast.walk(node):
        if not isinstance(item, (ast.Assign, ast.AnnAssign)) or not isinstance(item.value, ast.Call):
            continue
        call = item.value
        if not isinstance(call.func, ast.Attribute) or call.func.attr not in methods or not call.args:
            continue
        targets = item.targets if isinstance(item, ast.Assign) else [item.target]
        count = max((_unpack_count(target) for target in targets), default=0)
        name = _root_parameter(call.func.value, parameters)
        delimiter = _literal(call.args[0])
        if name and isinstance(delimiter, str) and delimiter and 1 < count <= maximum:
            part = str(policy.get("split_part") or "sample")
            candidates[name].append((_priority("split_unpack"), delimiter.join([part] * count), "ast_split_unpack"))


def _root_parameter(node: ast.AST, parameters: set[str]) -> str:
    if name := _direct_parameter(node, parameters):
        return name
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        return _root_parameter(node.func.value, parameters)
    return ""


def _unpack_count(node: ast.AST) -> int:
    return len(node.elts) if isinstance(node, (ast.Tuple, ast.List)) else 0


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
