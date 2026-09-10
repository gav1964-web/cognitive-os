"""AST traversal limited to one callable body."""

from __future__ import annotations

import ast
from collections.abc import Iterator


_NESTED_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def callable_scope_walk(function: ast.AST | None) -> Iterator[ast.AST]:
    if function is None:
        return
    yield function
    stack = list(reversed(getattr(function, "body", [])))
    while stack:
        node = stack.pop()
        if isinstance(node, _NESTED_SCOPES):
            stack.extend(reversed(_definition_time_children(node)))
            continue
        yield node
        stack.extend(reversed(list(ast.iter_child_nodes(node))))


def nested_definitions(function: ast.AST) -> list[ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef]:
    return [
        node for node in ast.walk(function)
        if node is not function and isinstance(node, _NESTED_SCOPES)
    ]


def _definition_time_children(node: ast.AST) -> list[ast.AST]:
    children = list(getattr(node, "decorator_list", []))
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        children.extend(node.args.defaults)
        children.extend(value for value in node.args.kw_defaults if value is not None)
    elif isinstance(node, ast.ClassDef):
        children.extend(node.bases)
        children.extend(keyword.value for keyword in node.keywords)
    return children
