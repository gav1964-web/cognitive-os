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
            continue
        yield node
        stack.extend(reversed(list(ast.iter_child_nodes(node))))
