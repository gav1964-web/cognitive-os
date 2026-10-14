"""Resolve test imports and preserve bounded, non-authoritative helper evidence."""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path

from .project_native_failure_module_resolution import _is_production_path, _python_module_path_any


def test_import_aliases(tree: ast.Module, *, project: Path, test_path: Path) -> dict:
    aliases = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for item in node.names:
                aliases[item.asname or item.name.split(".", 1)[0]] = (item.name, None)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                module = _relative_module(project, test_path, node.level, module)
            if not module:
                continue
            for item in node.names:
                if item.name != "*":
                    aliases[item.asname or item.name] = (module, item.name)
    return aliases


def _relative_module(project: Path, test_path: Path, level: int, module: str) -> str:
    project, test_path = project.resolve(), test_path.resolve()
    if not test_path.is_relative_to(project):
        return ""
    source_root = project / "src" if test_path.is_relative_to(project / "src") else project
    package = test_path.parent
    parts = list(package.relative_to(source_root).parts)
    if level > len(parts):
        return ""
    # A relative import requires a package, not a coincidentally named root module.
    current = package
    while current != source_root:
        if not (current / "__init__.py").is_file():
            return ""
        current = current.parent
    owner = parts[:len(parts) - level + 1]
    return ".".join([*owner, *module.split(".")]) if module else ".".join(owner)


def test_support_source(project: Path, function: ast.expr, aliases: dict) -> dict | None:
    """A helper body explains a blocked binding; it cannot authorize a repair target."""
    names = ast.unparse(function).split(".")
    binding = aliases.get(names[0])
    if not binding:
        return None
    module, imported = binding
    parts, symbols = module.split("."), names[1:]
    if imported:
        symbols.insert(0, imported)
    while symbols and _python_module_path_any(project, [*parts, symbols[0]]):
        parts.append(symbols.pop(0))
    path = _python_module_path_any(project, parts)
    if path is None or len(symbols) != 1 or _is_production_path(project, path):
        return None
    if not path.resolve().is_relative_to(project.resolve()) or path.stat().st_size > 100_000:
        return None
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8-sig")
        tree = ast.parse(text)
    except (OSError, UnicodeError, SyntaxError):
        return None
    matches = [node for node in tree.body
               if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == symbols[0]]
    if len(matches) != 1:
        return None
    node = matches[0]
    start = min([node.lineno, *[d.lineno for d in node.decorator_list]])
    excerpt = "\n".join(text.splitlines()[start - 1:node.end_lineno])
    imports = "\n".join(ast.get_source_segment(text, n) or "" for n in tree.body
                        if isinstance(n, (ast.Import, ast.ImportFrom)))
    return {"path": path.relative_to(project).as_posix(), "symbol": symbols[0],
            "file_sha256": hashlib.sha256(raw).hexdigest(), "start_line": start,
            "end_line": node.end_lineno, "excerpt": excerpt[:5000],
            "imports": imports[:2000], "excerpt_complete": len(excerpt) <= 5000 and len(imports) <= 2000,
            "authority": "diagnostic_only_not_a_production_target"}
