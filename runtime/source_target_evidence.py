"""Extract exact callable evidence for evaluation-only target clamps."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any


def source_target_evidence(project_dir: Path, target: str) -> dict[str, Any]:
    path_text, separator, symbol = target.partition(":")
    if not separator:
        return {}
    root = project_dir.resolve()
    path = (root / path_text).resolve()
    if not _within(path, root) or not path.is_file():
        return {}
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (OSError, UnicodeError, SyntaxError):
        return {}
    matches, node_kind = _callable_matches(tree, symbol)
    if len(matches) != 1:
        return {}
    node = matches[0]
    return {
        "source": target,
        "kind": "unknown",
        "node_kind": node_kind,
        "line": node.lineno,
        "loc": int(getattr(node, "end_lineno", node.lineno)) - node.lineno + 1,
        "signature": _signature(node),
        "snippet": {"text": ast.get_source_segment(source, node) or ast.unparse(node)},
        "claims": ["evaluation-only source evidence extracted from an exact project file and callable symbol"],
    }


def _callable_matches(
    tree: ast.Module, symbol: str
) -> tuple[list[ast.AsyncFunctionDef | ast.FunctionDef], str]:
    owner_name, separator, member_name = symbol.partition(".")
    if not separator:
        return ([
            node for node in tree.body
            if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef))
            and node.name == symbol
        ], "function")
    owners = [
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == owner_name
    ]
    if len(owners) != 1 or "." in member_name:
        return [], "method"
    return ([
        node for node in owners[0].body
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef))
        and node.name == member_name
    ], "method")


def _signature(node: ast.AsyncFunctionDef | ast.FunctionDef) -> dict[str, Any]:
    positional = [*node.args.posonlyargs, *node.args.args]
    return {
        "args": [{"name": arg.arg, "annotation": _annotation(arg.annotation)} for arg in positional],
        "kwonlyargs": [{"name": arg.arg, "annotation": _annotation(arg.annotation)} for arg in node.args.kwonlyargs],
        "returns": _annotation(node.returns),
        "async": isinstance(node, ast.AsyncFunctionDef),
    }


def _annotation(node: ast.AST | None) -> str:
    return ast.unparse(node) if node is not None else ""


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
