"""Infer executable samples from a callable's own source contract."""

from __future__ import annotations

import ast
from datetime import datetime
from pathlib import Path
from typing import Any

from .python_parser_compatibility import parse_compatible_source


def infer_argument_samples(path: Path, symbol: str) -> dict[str, dict[str, Any]]:
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
