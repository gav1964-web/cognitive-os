"""Infer executable samples from a callable's own source contract."""

from __future__ import annotations

import ast
import json
from collections import Counter
from pathlib import Path
from typing import Any

from .python_parser_compatibility import parse_compatible_source
from .function_invocation_patterns import upstream_test_extraction_policy
from .executable_acceptance_structural_samples import collect_structural_samples

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
    collect_structural_samples(tree, node, parameters, candidates)
    if project_root and project_root.is_dir():
        _collect_upstream_test_calls(project_root, path, symbol, node, candidates)
    return {
        name: {"value": value, "source": source}
        for name, rows in candidates.items()
        if rows
        for _, value, source in [max(rows, key=lambda row: row[0])]
    }


def _unique_callable(tree: ast.AST, symbol: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    owner, separator, callable_name = symbol.rpartition(".")
    callable_name = callable_name if separator else symbol
    if owner:
        matches = [
            item
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef) and node.name == owner
            for item in node.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            and item.name == callable_name
        ]
    else:
        matches = [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == callable_name
        ]
    return matches[0] if len(matches) == 1 else None


def _parameter_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    args = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
    return {item.arg for item in args if item.arg not in {"self", "cls"}}


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
