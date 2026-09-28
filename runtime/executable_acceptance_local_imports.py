"""Bounded substitutions for called factories from relative imports."""

from __future__ import annotations

import ast
from typing import Any

from .executable_acceptance_materializers import materialize
from .executable_acceptance_policy import source_isolation_policy


def replace_local_import_factories(
    imports: list[ast.stmt], nodes: list[ast.AST]
) -> tuple[list[ast.stmt], dict[str, Any], list[str]]:
    policy = dict(source_isolation_policy().get("local_import_factory_fixtures") or {})
    if not policy.get("enabled"):
        return imports, {}, []
    called = {
        value.func.id
        for node in nodes
        for item in ast.walk(node)
        for value in [item.value if isinstance(item, (ast.Assign, ast.AnnAssign)) else None]
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Name)
    }
    maximum = max(0, int(policy.get("maximum_symbols") or 0))
    selected: list[str] = []
    rewritten: list[ast.stmt] = []
    for node in imports:
        if not isinstance(node, ast.ImportFrom) or node.level <= 0:
            rewritten.append(node)
            continue
        kept: list[ast.alias] = []
        for alias in node.names:
            bound = str(alias.asname or alias.name)
            if bound in called and len(selected) < maximum:
                selected.append(bound)
            else:
                kept.append(alias)
        if kept:
            node.names = kept
            rewritten.append(node)
    fixture = str(policy.get("fixture") or "safe_symbolic_attribute")
    bindings = {name: materialize({"__fixture__": fixture}) for name in selected}
    return rewritten, bindings, selected
