"""Static distribution identity extraction from legacy setup.py files."""

from __future__ import annotations

import ast
from pathlib import Path


def setup_py_distribution_name(project: Path) -> str | None:
    path = project / "setup.py"
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, SyntaxError):
        return None
    names = {
        str(keyword.value.value).strip()
        for node in tree.body
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and _is_setup_call(node.value.func)
        for keyword in node.value.keywords
        if keyword.arg == "name"
        and isinstance(keyword.value, ast.Constant)
        and isinstance(keyword.value.value, str)
        and str(keyword.value.value).strip()
    }
    return next(iter(names)) if len(names) == 1 else None


def _is_setup_call(function: ast.expr) -> bool:
    return (
        isinstance(function, ast.Name) and function.id == "setup"
        or isinstance(function, ast.Attribute) and function.attr == "setup"
    )
