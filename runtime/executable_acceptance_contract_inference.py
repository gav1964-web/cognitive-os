"""Infer executable samples from a callable's own source contract."""

from __future__ import annotations

import ast
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from .python_parser_compatibility import parse_compatible_source
from .function_invocation_patterns import upstream_test_extraction_policy

_UNSAFE = object()


def infer_argument_samples(
    path: Path, symbol: str, *, project_root: Path | None = None
) -> dict[str, dict[str, Any]]:
    """Return high-confidence JSON samples keyed by parameter name."""
    try:
        tree, _ = parse_compatible_source(path.read_text(encoding="utf-8"), str(path))
    except (OSError, UnicodeError, SyntaxError):
        return {}
    node = _unique_callable(tree, symbol)
    if node is None:
        return {}
    parameters = _parameter_names(node)
    candidates: dict[str, list[tuple[int, Any, str]]] = {name: [] for name in parameters}
    for item in ast.walk(node):
        _collect_conversion(item, parameters, candidates)
        _collect_strptime(item, parameters, candidates)
        _collect_comparison(item, parameters, candidates)
    if project_root and project_root.is_dir():
        _collect_upstream_test_calls(project_root, path, symbol, node, candidates)
    return {
        name: {"value": value, "source": source}
        for name, rows in candidates.items()
        if rows
        for _, value, source in [max(rows, key=lambda row: row[0])]
    }


def _unique_callable(tree: ast.AST, symbol: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == symbol
    ]
    return matches[0] if len(matches) == 1 else None


def _parameter_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    args = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
    return {item.arg for item in args if item.arg not in {"self", "cls"}}


def _collect_conversion(
    node: ast.AST,
    parameters: set[str],
    candidates: dict[str, list[tuple[int, Any, str]]],
) -> None:
    if not isinstance(node, ast.Call) or not node.args or not isinstance(node.func, ast.Name):
        return
    name = _direct_parameter(node.args[0], parameters)
    if not name:
        return
    samples = {"float": "1.0", "int": "1"}
    if node.func.id in samples:
        candidates[name].append((80, samples[node.func.id], f"ast_conversion:{node.func.id}"))


def _collect_strptime(
    node: ast.AST,
    parameters: set[str],
    candidates: dict[str, list[tuple[int, Any, str]]],
) -> None:
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


def _collect_comparison(
    node: ast.AST,
    parameters: set[str],
    candidates: dict[str, list[tuple[int, Any, str]]],
) -> None:
    if not isinstance(node, ast.Compare):
        return
    expressions = [node.left, *node.comparators]
    for index, expression in enumerate(expressions):
        name = _direct_parameter(expression, parameters)
        if not name:
            continue
        constants = [_literal(item) for offset, item in enumerate(expressions) if offset != index]
        value = next((item for item in constants if _safe_scalar(item)), None)
        if value is not None:
            candidates[name].append((70, _comparison_sample(value), "ast_comparison_literal"))


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
    if isinstance(value, float):
        return value / 2
    return value


def _collect_upstream_test_calls(
    root: Path,
    source_path: Path,
    symbol: str,
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    candidates: dict[str, list[tuple[int, Any, str]]],
) -> None:
    parameters = [
        arg.arg
        for arg in [*function.args.posonlyargs, *function.args.args, *function.args.kwonlyargs]
        if arg.arg not in {"self", "cls"}
    ]
    observed: dict[str, Counter[str]] = {name: Counter() for name in parameters}
    values: dict[str, dict[str, Any]] = {name: {} for name in parameters}
    target_module = _target_module(root, source_path)
    policy = upstream_test_extraction_policy()
    if not policy.get("enabled"):
        return
    for test_path in _test_files(root, source_path, int(policy.get("max_files") or 500)):
        try:
            tree = ast.parse(test_path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, SyntaxError):
            continue
        aliases = _import_aliases(tree)
        calls = [
            item
            for item in ast.walk(tree)
            if isinstance(item, ast.Call) and _called_symbol(item, aliases, target_module) == symbol
        ]
        for call in calls:
            for name, value in _safe_call_arguments(call, parameters).items():
                key = json.dumps(value, sort_keys=True, separators=(",", ":"))
                observed[name][key] += 1
                values[name][key] = value
    for name, counts in observed.items():
        if not counts:
            continue
        key, count = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0]
        value = values[name][key]
        is_model = isinstance(value, dict) and value.get("__fixture__") == "declared_model"
        priority = int(policy.get("candidate_priority") or 120)
        candidates[name].append((priority + min(count, 20), value, f"upstream_test_call:{'constructor' if is_model else 'literal'}"))


def _test_files(root: Path, source_path: Path, max_files: int):
    seen = 0
    for path in sorted(root.rglob("*.py")):
        if path.resolve() == source_path.resolve():
            continue
        rel = path.relative_to(root).as_posix().lower()
        if not (path.name.startswith("test_") or "/tests/" in f"/{rel}"):
            continue
        yield path
        seen += 1
        if seen >= max_files:
            return


def _called_symbol(call: ast.Call, aliases: dict[str, str], target_module: str) -> str:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if not isinstance(call.func, ast.Attribute) or not isinstance(call.func.value, ast.Name):
        return ""
    imported = aliases.get(call.func.value.id, "")
    return call.func.attr if imported == target_module else ""


def _target_module(root: Path, source_path: Path) -> str:
    relative = source_path.resolve().relative_to(root.resolve()).with_suffix("")
    parts = list(relative.parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _import_aliases(tree: ast.AST) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                aliases[str(item.asname or item.name.split(".")[0])] = str(item.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            for item in node.names:
                aliases[str(item.asname or item.name)] = f"{node.module}.{item.name}"
    return aliases


def _safe_call_arguments(call: ast.Call, parameters: list[str]) -> dict[str, Any]:
    bound: dict[str, Any] = {}
    for index, node in enumerate(call.args):
        if index >= len(parameters):
            break
        value = _safe_test_value(node)
        if value is not _UNSAFE:
            bound[parameters[index]] = value
    for keyword in call.keywords:
        if keyword.arg not in parameters:
            continue
        value = _safe_test_value(keyword.value)
        if value is not _UNSAFE:
            bound[str(keyword.arg)] = value
    return bound


def _safe_test_value(node: ast.AST) -> Any:
    try:
        value = ast.literal_eval(node)
    except (ValueError, TypeError):
        value = _UNSAFE
    if value is not _UNSAFE and _json_safe(value):
        return value
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
        return _UNSAFE
    fields = {}
    for item in node.keywords:
        item_value = _safe_test_value(item.value)
        if item.arg and item_value is not _UNSAFE:
            fields[str(item.arg)] = item_value
    if not fields or len(fields) != len(node.keywords) or node.args:
        return _UNSAFE
    return {"__fixture__": "declared_model", "type": node.func.id, "fields": fields}


def _json_safe(value: Any) -> bool:
    try:
        json.dumps(value)
    except (TypeError, ValueError):
        return False
    return value is None or isinstance(value, (str, int, float, bool, list, tuple, dict))
