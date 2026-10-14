"""Conservative AST evidence for receiver-bound dynamic dispatch."""

from __future__ import annotations

import ast

from runtime.source_ast_scope import callable_scope_walk


def is_receiver_request_dispatch(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Call):
        return False
    lookup = node.func
    if not isinstance(lookup.func, ast.Name) or lookup.func.id.lower() != "getattr":
        return False
    receiver_bound = bool(
        lookup.args and isinstance(lookup.args[0], ast.Name) and lookup.args[0].id in {"self", "cls"}
    )
    selector_bound = len(lookup.args) > 1 and isinstance(lookup.args[1], ast.Name)
    request_values = any(
        keyword.arg is None and "request" in ast.unparse(keyword.value).lower()
        for keyword in node.keywords
    )
    return receiver_bound and selector_bound and request_values


def has_receiver_request_dispatch(node: ast.AST) -> bool:
    return any(is_receiver_request_dispatch(item) for item in callable_scope_walk(node))
