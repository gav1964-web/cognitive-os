"""Infer bounded cross-file effects and contract slices for local callables."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from .source_side_effect_inference import infer_ast_side_effects
from .python_source_files import iter_python_source_files


def project_transitive_effects(root: Path, *, max_files: int = 80, max_depth: int = 2) -> dict[str, dict[str, Any]]:
    nodes = _project_nodes(root, max_files=max_files)
    by_symbol: dict[str, list[str]] = {}
    for source, row in nodes.items():
        by_symbol.setdefault(str(row["symbol"]), []).append(source)
    edges: dict[str, set[str]] = {source: set() for source in nodes}
    for source, row in nodes.items():
        for symbol in row["calls"]:
            matches = by_symbol.get(symbol, [])
            if len(matches) == 1 and matches[0] != source:
                edges[source].add(matches[0])
    return {
        source: _source_effect_report(source, nodes, edges, max_depth=max_depth)
        for source in nodes
    }


def _project_nodes(root: Path, *, max_files: int) -> dict[str, dict[str, Any]]:
    nodes: dict[str, dict[str, Any]] = {}
    paths = list(iter_python_source_files(root, limit=max_files))
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(text)
            relative = path.relative_to(root).as_posix()
        except (OSError, SyntaxError, ValueError):
            continue
        lines = text.splitlines(keepends=True)
        for qualified_name, node in _module_callables(tree):
            source = f"{relative}:{qualified_name}"
            nodes[source] = {
                "symbol": node.name,
                "calls": _called_symbols(node),
                "effects": set(infer_ast_side_effects(node, _node_text(lines, node))),
            }
    return nodes


def _module_callables(tree: ast.Module) -> list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    callables = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            callables.append((node.name, node))
        elif isinstance(node, ast.ClassDef):
            callables.extend(
                (f"{node.name}.{item.name}", item)
                for item in node.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            )
    return callables


def _node_text(source_lines: list[str], node: ast.AST) -> str:
    start = getattr(node, "lineno", None)
    end = getattr(node, "end_lineno", None)
    if not isinstance(start, int) or not isinstance(end, int):
        return ""
    return "".join(source_lines[max(0, start - 1) : end])


def _source_effect_report(
    source: str,
    nodes: dict[str, dict[str, Any]],
    edges: dict[str, set[str]],
    *,
    max_depth: int,
) -> dict[str, Any]:
    effects = set(nodes[source]["effects"])
    chains: list[dict[str, Any]] = []
    slice_sources = {source}

    def visit(current: str, path: list[str], depth: int) -> None:
        if depth >= max_depth:
            return
        for callee in sorted(edges.get(current, set())):
            if callee in path:
                continue
            slice_sources.add(callee)
            direct = set(nodes[callee]["effects"])
            effects.update(direct)
            for effect in sorted(direct):
                chains.append({"effect": effect, "call_chain": [*path, callee]})
            visit(callee, [*path, callee], depth + 1)

    visit(source, [source], 0)
    result: dict[str, Any] = {}
    inherited = effects - set(nodes[source]["effects"])
    if inherited:
        result["transitive_side_effects"] = sorted(inherited)
        result["transitive_effect_chains"] = chains[:12]
    if len(slice_sources) > 1:
        result["contract_slice_sources"] = sorted(slice_sources)[:8]
    return result


def _called_symbols(node: ast.AST) -> set[str]:
    symbols = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
            symbols.add(child.func.id)
        elif (
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Attribute)
            and isinstance(child.func.value, ast.Name)
            and child.func.value.id in {"self", "cls"}
        ):
            symbols.add(child.func.attr)
    return symbols


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Call):
        return _call_name(node.func)
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""
