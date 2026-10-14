"""Infer argument fixtures from declared base-class method contracts."""

from __future__ import annotations

import ast
from typing import Any

Candidates = dict[str, list[tuple[int, Any, str]]]
FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


def add_inherited_method_samples(
    tree: ast.Module,
    node: FunctionNode,
    parameters: set[str],
    candidates: Candidates,
    *,
    priority: int,
    profiles: list[dict[str, Any]],
) -> None:
    owner = next(
        (
            item
            for item in tree.body
            if isinstance(item, ast.ClassDef) and any(member is node for member in item.body)
        ),
        None,
    )
    if owner is None:
        return
    bases = {_expression_name(base) for base in owner.bases}
    for profile in profiles:
        parameter = str(profile.get("parameter") or "")
        base_token = str(profile.get("base_contains") or "")
        methods = {str(item) for item in profile.get("methods") or []}
        fixture = str(profile.get("fixture") or "")
        if (
            parameter in parameters
            and node.name in methods
            and fixture
            and any(base_token in base for base in bases)
        ):
            candidates[parameter].append((
                priority,
                {"__fixture__": fixture},
                f"ast_inherited_method_contract:{base_token}.{node.name}",
            ))


def _expression_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _expression_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""
