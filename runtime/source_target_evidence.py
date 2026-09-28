"""Extract exact callable evidence for evaluation-only target clamps."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from .python_parser_compatibility import parse_compatible_source
from .source_contract_semantics import infer_source_contract


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
        tree, parser_mode = parse_compatible_source(source, path_text)
    except (OSError, UnicodeError, SyntaxError):
        return {}
    matches, node_kind, owner_class = _callable_matches(tree, symbol)
    if len(matches) != 1:
        return {}
    node = matches[0]
    signature = _signature(node)
    snippet_text = ast.get_source_segment(source, node) or ast.unparse(node)
    structural = infer_source_contract({"signature": signature, "snippet": snippet_text})
    target_binding = "method_symbol" if node_kind == "method" else "function_symbol"
    return {
        "source": target,
        "kind": "unknown",
        "node_kind": node_kind,
        "line": node.lineno,
        "loc": int(getattr(node, "end_lineno", node.lineno)) - node.lineno + 1,
        "signature": signature,
        "snippet": {
            "text": snippet_text,
            "signature": signature,
            "target_binding": target_binding,
            "owner_class": owner_class,
            "decorators": [_annotation(value) for value in node.decorator_list],
            "structural_contract": structural,
        },
        **({"parser_mode": parser_mode} if parser_mode else {}),
        "claims": ["evaluation-only source evidence extracted from an exact project file and callable symbol"],
    }


def _callable_matches(
    tree: ast.Module, symbol: str
) -> tuple[list[ast.AsyncFunctionDef | ast.FunctionDef], str, str]:
    owner_name, separator, member_name = symbol.partition(".")
    if not separator:
        top_level = [
            node for node in tree.body
            if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef))
            and node.name == symbol
        ]
        if top_level:
            return top_level, "function", ""
        methods = [
            (member, owner.name)
            for owner in tree.body if isinstance(owner, ast.ClassDef)
            for member in owner.body
            if isinstance(member, (ast.AsyncFunctionDef, ast.FunctionDef))
            and member.name == symbol
        ]
        return ([methods[0][0]], "method", methods[0][1]) if len(methods) == 1 else ([], "method", "")
    owners = [
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == owner_name
    ]
    if len(owners) != 1 or "." in member_name:
        return [], "method", owner_name
    return ([
        node for node in owners[0].body
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef))
        and node.name == member_name
    ], "method", owner_name)


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
