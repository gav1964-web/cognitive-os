"""Conservative AST evidence for observable callable side effects."""

from __future__ import annotations

import ast
from typing import Any


_UNIT_OF_WORK_NAMES = {"session", "db", "database", "unit_of_work", "uow"}
_DATABASE_WRITE_CALLS = {"add", "append", "delete", "execute_write", "executemany", "flush", "commit"}


def observed_side_effects(function: ast.AST | None, args: list[dict[str, Any]]) -> list[str]:
    if function is None:
        return []
    argument_names = {str(row.get("name") or "").lower() for row in args}
    effects = set()
    for node in ast.walk(function):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        owner = _root_name(node.func.value).lower()
        operation = node.func.attr.lower()
        if owner in argument_names & _UNIT_OF_WORK_NAMES and operation in _DATABASE_WRITE_CALLS:
            effects.add("database")
    return sorted(effects)


def _root_name(node: ast.AST) -> str:
    while isinstance(node, (ast.Attribute, ast.Call)):
        node = node.value if isinstance(node, ast.Attribute) else node.func
    return node.id if isinstance(node, ast.Name) else ""
