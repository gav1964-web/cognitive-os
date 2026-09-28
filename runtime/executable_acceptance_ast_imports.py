"""Select imports required by a source-isolated callable."""

from __future__ import annotations

import ast
import copy


def needed_import_nodes(tree: ast.Module, nodes: list[ast.AST]) -> list[ast.stmt]:
    loaded = {name for node in nodes for name in loaded_names(node)}
    imports: list[ast.stmt] = []
    for node in _module_scope_nodes(tree.body):
        wildcard = isinstance(node, ast.ImportFrom) and any(alias.name == "*" for alias in node.names)
        if isinstance(node, (ast.Import, ast.ImportFrom)) and not wildcard and _bound_names(node) & loaded:
            selected = copy.deepcopy(node)
            selected.names = [
                alias
                for alias in selected.names
                if (alias.asname or alias.name.split(".", 1)[0]) in loaded
            ]
            if selected.names:
                imports.append(selected)
    return imports


def loaded_names(node: ast.AST) -> set[str]:
    return {
        item.id
        for item in ast.walk(node)
        if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load)
    }


def needed_class_members(class_node: ast.ClassDef, selected: set[str]) -> list[ast.AST]:
    methods = [
        node
        for node in class_node.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in selected
    ]
    loaded = {name for node in methods for name in loaded_names(node)}
    class_attributes = {
        item.attr
        for method in methods
        for item in ast.walk(method)
        if isinstance(item, ast.Attribute)
        and isinstance(item.value, ast.Name)
        and item.value.id in {class_node.name, "cls"}
    }
    members: list[ast.AST] = []
    for node in class_node.body:
        if node in methods:
            members.append(copy.deepcopy(node))
        elif isinstance(node, (ast.Assign, ast.AnnAssign)) and _assigned_names(node) & (loaded | class_attributes):
            members.append(copy.deepcopy(node))
    return members


def _module_scope_nodes(nodes: list[ast.stmt]):
    for node in nodes:
        yield node
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        for field in ("body", "orelse", "finalbody"):
            children = getattr(node, field, None)
            if isinstance(children, list):
                yield from _module_scope_nodes(children)
        for handler in getattr(node, "handlers", []):
            yield from _module_scope_nodes(handler.body)


def _bound_names(node: ast.Import | ast.ImportFrom) -> set[str]:
    return {alias.asname or alias.name.split(".", 1)[0] for alias in node.names}


def _assigned_names(node: ast.Assign | ast.AnnAssign) -> set[str]:
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    return {target.id for target in targets if isinstance(target, ast.Name)}
