"""Common helpers for executable-acceptance structural sample inference."""

from __future__ import annotations

import ast
from typing import Any

from .executable_acceptance_policy import structural_sample_policy

Candidates = dict[str, list[tuple[int, Any, str]]]
FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


def _settings() -> dict[str, Any]:
    return structural_sample_policy()


def _priority(name: str) -> int:
    return int(dict(_settings().get("priorities") or {})[name])


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
