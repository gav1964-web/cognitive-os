"""Detect names that prevent a source symbol from standing alone."""

from __future__ import annotations

import ast
import builtins
from typing import Any

from runtime.technical_spec_policy import load_technical_spec_policy


def standalone_dependency_facts(tree: ast.Module, node: ast.AST) -> dict[str, Any]:
    imports = _import_bindings(tree)
    module_definitions = {
        item.name for item in tree.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }
    module_state = _module_state_names(tree)
    local = _local_names(node)
    loaded = {
        item.id for item in ast.walk(node)
        if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load)
    }
    known = local | imports | module_definitions | module_state | set(dir(builtins))
    unresolved = sorted(loaded - known)
    state_dependencies = sorted(loaded & module_state)
    callable_dependencies = sorted(loaded & module_definitions)
    return {
        "unresolved_runtime_names": unresolved,
        "module_state_dependencies": state_dependencies,
        "module_callable_dependencies": callable_dependencies,
    }


def blocking_runtime_names(names: list[str]) -> list[str]:
    policy = dict(load_technical_spec_policy().get("dependency_readiness") or {})
    unsupported = {str(item) for item in list(policy.get("unsupported_runtime_names") or [])}
    return sorted(set(names) & unsupported)


def _import_bindings(tree: ast.Module) -> set[str]:
    names = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            names.update(alias.asname or alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names if alias.name != "*")
    return names


def _module_state_names(tree: ast.Module) -> set[str]:
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
                names.add(child.id)
    return names


def _local_names(node: ast.AST) -> set[str]:
    names = {
        item.id for item in ast.walk(node)
        if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Store)
    }
    names.update(item.arg for item in ast.walk(node) if isinstance(item, ast.arg))
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        names.update(
            arg.arg for arg in [
                *node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs,
                *([node.args.vararg] if node.args.vararg else []),
                *([node.args.kwarg] if node.args.kwarg else []),
            ]
        )
        names.add(node.name)
    return names
