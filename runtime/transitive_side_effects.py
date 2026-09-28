"""Resolve side effects through bounded same-module call chains."""

from __future__ import annotations

import ast
from typing import Any

from .source_side_effect_inference import infer_ast_side_effects


def infer_transitive_side_effects(tree: ast.AST, target: ast.AST, *, max_depth: int = 4) -> dict[str, Any]:
    functions = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    effects: set[str] = set()
    chains: list[dict[str, Any]] = []
    visited: set[str] = set()

    def visit(node: ast.AST, path: list[str], depth: int) -> None:
        name = str(getattr(node, "name", "<callable>"))
        if name in visited or depth > max_depth:
            return
        visited.add(name)
        direct = infer_ast_side_effects(node, ast.unparse(node))
        effects.update(direct)
        for effect in direct:
            chains.append({"effect": effect, "call_chain": [*path, name]})
        for called in _local_call_names(node):
            callee = functions.get(called)
            if callee is not None:
                visit(callee, [*path, name], depth + 1)

    visit(target, [], 0)
    return {"effects": sorted(effects), "chains": chains}


def _local_call_names(node: ast.AST) -> set[str]:
    names = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        name = _call_name(child.func)
        if name:
            names.add(name.rsplit(".", 1)[-1])
    return names


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""
