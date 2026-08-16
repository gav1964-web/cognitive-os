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
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            source = f"{relative}:{node.name}"
            nodes[source] = {
                "symbol": node.name,
                "calls": _called_symbols(node),
                "effects": set(infer_ast_side_effects(node, _node_text(text, node))),
            }
    return nodes


def _node_text(source: str, node: ast.AST) -> str:
    segment = ast.get_source_segment(source, node)
    if segment is not None:
        return segment
    try:
        return ast.unparse(node)
    except (TypeError, ValueError):
        return ""


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
