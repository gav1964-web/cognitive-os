"""Apply configured stdlib import fallbacks inside source isolation."""

from __future__ import annotations

import ast
import copy
from typing import Any


def apply_import_fallbacks(
    imports: list[ast.stmt], fallbacks: list[dict[str, Any]],
) -> list[ast.stmt]:
    rules = {
        (str(row.get("module") or ""), str(row.get("name") or "")): row
        for row in fallbacks
        if row.get("module") and row.get("name")
    }
    rewritten: list[ast.stmt] = []
    for original in imports:
        node = copy.deepcopy(original)
        if not isinstance(node, ast.ImportFrom):
            rewritten.append(node)
            continue
        matched = [alias for alias in node.names if (str(node.module or ""), alias.name) in rules]
        if not matched:
            rewritten.append(node)
            continue
        node.names = [alias for alias in node.names if alias not in matched]
        if node.names:
            rewritten.append(node)
        for alias in matched:
            rule = rules[(str(node.module or ""), alias.name)]
            fallback_name = str(rule.get("fallback_name") or "")
            fallback_attribute = str(rule.get("fallback_attribute") or "")
            if not fallback_name or not fallback_attribute:
                continue
            rewritten.append(ast.ImportFrom(
                module=node.module,
                names=[ast.alias(name=fallback_name)],
                level=node.level,
            ))
            rewritten.append(ast.Assign(
                targets=[ast.Name(id=alias.asname or alias.name, ctx=ast.Store())],
                value=ast.Attribute(
                    value=ast.Name(id=fallback_name, ctx=ast.Load()),
                    attr=fallback_attribute,
                    ctx=ast.Load(),
                ),
            ))
    return rewritten


def configured_import_fallbacks(imports: list[ast.stmt]) -> list[ast.stmt]:
    from .executable_acceptance_policy import source_isolation_policy

    return apply_import_fallbacks(
        imports, list(source_isolation_policy().get("stdlib_import_fallbacks") or [])
    )
