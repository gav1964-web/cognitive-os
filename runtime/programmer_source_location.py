"""Bounded source excerpts with full-file line locations for Programmer prompts."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from .programmer_python_symbols import qualified_function_matches


def source_location(project_dir: Path, target: str) -> dict[str, Any]:
    path_text, _, symbol = target.partition(":")
    path = (project_dir / path_text).resolve()
    try:
        path.relative_to(project_dir.resolve())
    except ValueError:
        return _empty()
    if not path.is_file():
        return _empty()
    source = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {"excerpt": source[:4000], "start_line": 1, "context": source[:6000], "context_start_line": 1}
    matches = qualified_function_matches(tree, symbol)
    if len(matches) == 1:
        node = matches[0]
        lines = source.splitlines()
        excerpt = "\n".join(lines[node.lineno - 1 : (node.end_lineno or node.lineno)])[:4000]
        context_start = max(node.lineno - 21, 0)
        context_end = min((node.end_lineno or node.lineno) + 20, len(lines))
        context = "\n".join(lines[context_start:context_end])[:6000]
        return {
            "excerpt": excerpt,
            "start_line": node.lineno,
            "context": context,
            "context_start_line": context_start + 1,
        }
    return {"excerpt": source[:4000], "start_line": 1, "context": source[:6000], "context_start_line": 1}


def _empty() -> dict[str, Any]:
    return {"excerpt": "", "start_line": 0, "context": "", "context_start_line": 0}
