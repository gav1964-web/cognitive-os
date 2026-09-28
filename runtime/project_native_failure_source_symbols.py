"""Source-symbol lookup helpers for project-native failure binding."""

from __future__ import annotations

import ast
from pathlib import Path

from .project_native_failure_module_resolution import _python_module_path, _is_production_path

def _source_symbol_target(project: Path, path: Path, symbol: str) -> tuple[Path, str] | None:
    if not path.resolve().is_relative_to(project.resolve()) or not _is_production_path(project, path):
        return None
    if _source_defines_symbol(path, symbol):
        return path, symbol
    if path.name != "__init__.py":
        return None
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return None
    candidates: list[tuple[Path, str]] = []
    exported_name = symbol.split(".", 1)[0]
    suffix = symbol.partition(".")[2]
    if any(isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id == exported_name
           for statement in tree.body if not isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
           for node in ast.walk(statement)):
        return None
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom) or node.level not in {0, 1}:
            continue
        if not node.module:
            continue
        module = node.module.split(".")
        candidate = (_python_module_path(project, module) if node.level == 0
                     else path.parent.joinpath(*module).with_suffix(".py"))
        if candidate is None or not candidate.resolve().is_relative_to(project.resolve()):
            continue
        if not _is_production_path(project, candidate):
            continue
        for item in node.names:
            if item.name == '*' and not _wildcard_exports(candidate, exported_name):
                continue
            if item.name == "*" or (item.asname or item.name) == exported_name:
                source_symbol = (f"{item.name}.{suffix}" if suffix else item.name) if item.name != "*" else symbol
            else:
                continue
            if candidate.is_file() and _source_defines_symbol(candidate, source_symbol):
                candidates.append((candidate, source_symbol))
    unique = list(dict.fromkeys(candidates))
    return unique[0] if len(unique) == 1 else None


def _wildcard_exports(path: Path, name: str) -> bool:
    """Only accept literal __all__ or the ordinary public-name convention."""
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'))
        uses = [n for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == '__all__']
        if not uses:
            return not name.startswith('_')
        assignments = [n for n in tree.body if isinstance(n, ast.Assign)
                       and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and n.targets[0].id == '__all__']
        if len(uses) != 1 or len(assignments) != 1:
            return False
        exported = ast.literal_eval(assignments[0].value)
        return type(exported) in (list, tuple) and all(type(n) is str for n in exported) and name in exported
    except (OSError, UnicodeError, SyntaxError, ValueError, TypeError):
        return False

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
