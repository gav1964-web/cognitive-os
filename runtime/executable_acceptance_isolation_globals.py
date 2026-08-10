"""Module-level AST closure helpers for source-isolated acceptance."""

from __future__ import annotations

import ast
import copy


def isolated_global_nodes(tree: ast.Module, nodes: list[ast.AST], class_name: str) -> list[ast.stmt]:
    top = {getattr(item, "name", ""): item for item in tree.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))}
    other = [item for item in tree.body if isinstance(item, (ast.Assign, ast.AnnAssign))]
    selected: list[ast.stmt] = []
    seen: set[str] = set()
    loaded = {name for node in nodes for name in loaded_names(node)} - {class_name}
    changed = True
    while changed:
        changed = False
        for item in [*top.values(), *other]:
            names = {getattr(item, "name", "")} if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) else assigned_names(item)
            if names & loaded and not names <= seen:
                copied = isolated_member(item)
                selected.append(copied)
                seen.update(names)
                loaded.update(loaded_names(copied))
                changed = True
    return selected


def isolated_member(item: ast.AST) -> ast.AST:
    copied = copy.deepcopy(item)
    if isinstance(copied, (ast.FunctionDef, ast.AsyncFunctionDef)):
        copied.decorator_list = []
        copied.returns = None
        for arg in list(copied.args.posonlyargs) + list(copied.args.args) + list(copied.args.kwonlyargs):
            arg.annotation = None
        if copied.args.vararg:
            copied.args.vararg.annotation = None
        if copied.args.kwarg:
            copied.args.kwarg.annotation = None
    return copied


def loaded_names(node: ast.AST) -> set[str]:
    return {item.id for item in ast.walk(node) if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load)}


def assigned_names(node: ast.AST) -> set[str]:
    targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
    return {item.id for target in targets for item in ast.walk(target) if isinstance(item, ast.Name)}
