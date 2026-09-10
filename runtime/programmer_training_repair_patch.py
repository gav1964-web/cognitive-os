"""Exact, training-only edits for consumed defect replay cases."""

from __future__ import annotations

import ast
from typing import Any


def training_repair_patch(
    source: str, *, symbol: str, operation_kind: str, recipe: dict[str, Any]
) -> dict[str, Any] | None:
    if recipe.get("authority") != "training_only":
        return None
    if operation_kind == "guard_empty_materialized_fast_path":
        return _guard_empty_materialized_fast_path(source, symbol)
    if operation_kind == "require_left_token_boundary_for_numeric_range":
        return _require_left_token_boundary(source, symbol)
    return None


def _guard_empty_materialized_fast_path(source: str, symbol: str) -> dict[str, Any] | None:
    old = "if maxsplit == 0:\n        yield list(iterable)\n        return"
    new = "if maxsplit == 0:\n        buf = list(iterable)\n        if buf:\n            yield buf\n        return"
    patched = source
    affected = []
    for name in ("split_before", "split_after", "split_when"):
        result = _replace_in_unique_function(patched, name, old, new)
        if result is not None:
            patched = str(result["source"])
            affected.append(name)
    if symbol.rsplit(".", 1)[-1] not in affected or len(affected) < 2:
        return None
    return {
        "source": patched,
        "source_precondition": old,
        "affected_symbols": affected,
    }


def _require_left_token_boundary(source: str, symbol: str) -> dict[str, Any] | None:
    old = (
        "            ( \\d+ ) - ( \\d+ )   # closed range: start-end\n"
        "            |\n"
        "            ( \\d+ ) -           # right-open range: start-"
    )
    new = (
        "            (?<! [\\w.] )          # do not start inside a name/version\n"
        "            (?:\n"
        "                ( \\d+ ) - ( \\d+ )   # closed range: start-end\n"
        "                |\n"
        "                ( \\d+ ) -           # right-open range: start-\n"
        "            )"
    )
    return _replace_in_unique_function(source, symbol, old, new)


def _replace_in_unique_function(
    source: str, symbol: str, old: str, new: str
) -> dict[str, Any] | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    leaf = symbol.rsplit(".", 1)[-1]
    matches = [
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == leaf
    ]
    if len(matches) != 1:
        return None
    function = matches[0]
    lines = source.splitlines(keepends=True)
    start = int(function.lineno) - 1
    end = int(getattr(function, "end_lineno", function.lineno))
    body = "".join(lines[start:end])
    newline = "\r\n" if "\r\n" in source else "\n"
    normalized = body.replace("\r\n", "\n")
    if normalized.count(old) != 1:
        return None
    replacement = normalized.replace(old, new, 1).replace("\n", newline)
    patched = "".join(lines[:start]) + replacement + "".join(lines[end:])
    try:
        ast.parse(patched)
    except SyntaxError:
        return None
    return {"source": patched, "source_precondition": old}
