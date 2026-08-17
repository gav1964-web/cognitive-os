"""Module-level AST closure helpers for source-isolated acceptance."""

from __future__ import annotations

import ast
import builtins
import copy
from typing import Any


def isolated_global_nodes(tree: ast.Module, nodes: list[ast.AST], class_name: str) -> list[ast.stmt]:
    top = {
        getattr(item, "name", ""): item
        for item in tree.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }
    other = [item for item in tree.body if isinstance(item, (ast.Assign, ast.AnnAssign))]
    selected: list[ast.stmt] = []
    seen: set[str] = set()
    loaded = {name for node in nodes for name in loaded_names(node)} - {class_name}
    changed = True
    while changed:
        changed = False
        for item in [*top.values(), *other]:
            names = {getattr(item, "name", "")} if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) else assigned_names(item)
            if names & loaded and not names <= seen:
                selected.append(item)
                seen.update(names)
                loaded.update(loaded_names(item))
                changed = True
    return [isolated_member(item) for item in tree.body if item in selected]


def isolated_member(item: ast.AST) -> ast.AST:
    copied = copy.deepcopy(item)
    if isinstance(copied, ast.Assign) and isinstance(copied.value, ast.Call):
        unpack_count = _unpack_target_count(copied.targets)
        if unpack_count:
            copied.value = ast.Tuple(
                elts=[ast.Constant(value=False) for _ in range(unpack_count)],
                ctx=ast.Load(),
            )
    if isinstance(copied, (ast.FunctionDef, ast.AsyncFunctionDef)):
        copied.decorator_list = []
        copied.returns = None
        for arg in list(copied.args.posonlyargs) + list(copied.args.args) + list(copied.args.kwonlyargs):
            arg.annotation = None
        if copied.args.vararg:
            copied.args.vararg.annotation = None
        if copied.args.kwarg:
            copied.args.kwarg.annotation = None
    elif isinstance(copied, ast.ClassDef):
        copied.bases = []
        copied.keywords = []
        copied.decorator_list = []
        copied.body = [isolated_member(node) for node in copied.body]
    return copied


def _unpack_target_count(targets: list[ast.expr]) -> int:
    if len(targets) != 1 or not isinstance(targets[0], (ast.Tuple, ast.List)):
        return 0
    return len(targets[0].elts)


def loaded_names(node: ast.AST) -> set[str]:
    return {item.id for item in ast.walk(node) if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load)}


def assigned_names(node: ast.AST) -> set[str]:
    targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
    return {item.id for target in targets for item in ast.walk(target) if isinstance(item, ast.Name)}


def install_unresolved_wildcard_names(
    tree: ast.Module,
    nodes: list[ast.AST],
    namespace: dict[str, Any],
) -> list[str]:
    has_wildcard = any(
        isinstance(node, ast.ImportFrom) and any(alias.name == "*" for alias in node.names)
        for node in tree.body
    )
    if not has_wildcard:
        return []
    loaded = {name for node in nodes for name in loaded_names(node)}
    bound = {name for node in nodes for name in _callable_bound_names(node)}
    unresolved = sorted(loaded - bound - set(namespace) - set(dir(builtins)))
    if not unresolved:
        return []
    from .executable_acceptance_materializers import materialize

    for name in unresolved:
        namespace[name] = materialize({"__fixture__": "safe_symbolic_attribute"})
    return unresolved


def install_configured_global_fixtures(nodes: list[ast.AST], namespace: dict[str, Any]) -> list[str]:
    from .executable_acceptance_materializers import materialize
    from .executable_acceptance_policy import source_isolation_policy

    loaded = {name for node in nodes for name in loaded_names(node)}
    profiles = dict(source_isolation_policy().get("global_symbol_fixtures") or {})
    installed = sorted(name for name in profiles if name in loaded and name in namespace)
    for name in installed:
        namespace[name] = materialize(profiles[name])
    return installed


def _callable_bound_names(node: ast.AST) -> set[str]:
    names = {
        item.id
        for item in ast.walk(node)
        if isinstance(item, ast.Name) and isinstance(item.ctx, (ast.Store, ast.Param))
    }
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        names.update(arg.arg for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs])
    return names
