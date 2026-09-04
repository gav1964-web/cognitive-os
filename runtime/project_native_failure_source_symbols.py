"""Source-symbol lookup helpers for project-native failure binding."""

from __future__ import annotations

import ast
from pathlib import Path

def _source_defines_symbol(path: Path, symbol: str) -> bool:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return False
    current: list[ast.stmt] = list(tree.body)
    for part in symbol.split("."):
        node = next(
            (item for item in current if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and item.name == part),
            None,
        )
        if node is None:
            return False
        current = list(node.body) if isinstance(node, ast.ClassDef) else []
    return True

def _symbol_at_line(path: Path, line: int) -> str | None:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return None
    candidates = []
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if int(node.lineno) <= line <= int(getattr(node, "end_lineno", node.lineno)):
            parent = parents.get(node)
            name = f"{parent.name}.{node.name}" if isinstance(parent, ast.ClassDef) else node.name
            candidates.append((int(getattr(node, "end_lineno", node.lineno)) - int(node.lineno), name))
    return min(candidates)[1] if candidates else None
