"""Policy-driven argument types inferred from qualified calls."""

from __future__ import annotations

import ast

from runtime.source_ast_scope import callable_scope_walk
from runtime.technical_spec_policy import load_technical_spec_policy


def qualified_call_argument_types(
    function: ast.AST, known_names: set[str]
) -> dict[str, str]:
    section = dict(load_technical_spec_policy().get("contract_type_inference") or {})
    rules = {
        str(name).lower(): str(value)
        for name, value in dict(section.get("qualified_call_argument_types") or {}).items()
    }
    inferred: dict[str, str] = {}
    for node in callable_scope_walk(function):
        if not isinstance(node, ast.Call):
            continue
        inferred_type = rules.get(_qualified_name(node.func).lower())
        if not inferred_type:
            continue
        for argument in node.args:
            for child in ast.walk(argument):
                if isinstance(child, ast.Name) and child.id in known_names:
                    inferred[child.id] = inferred_type
    return inferred


def _qualified_name(node: ast.AST) -> str:
    parts = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return ""
    return ".".join([current.id, *reversed(parts)])
