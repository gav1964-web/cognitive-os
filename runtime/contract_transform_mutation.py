"""Build reversible identity mutations from config-backed transform operators."""

from __future__ import annotations

import ast
from typing import Any

from .contract_transform_operators import load_contract_transform_operators


def observed_operator(node: ast.FunctionDef | ast.AsyncFunctionDef, arg: str) -> str | None:
    """Return the exact configured operator implemented by a one-return callable."""
    body = [item for item in node.body if not _doc_expr(item)]
    if len(body) != 1 or not isinstance(body[0], ast.Return) or body[0].value is None:
        return None
    actual = ast.dump(body[0].value, include_attributes=False)
    catalog = load_contract_transform_operators()
    for row in list(catalog.get("operators") or []):
        if not isinstance(row, dict):
            continue
        expression = str(row.get("expression_template") or "").replace("{arg}", arg)
        try:
            expected = ast.parse(expression, mode="eval").body
        except SyntaxError:
            continue
        if actual == ast.dump(expected, include_attributes=False):
            return str(row.get("id") or "") or None
    return None


def identity_mutation_source(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    arg: str,
    *,
    function_name: str | None = None,
) -> str:
    clone = ast.parse(ast.unparse(node)).body[0]
    if not isinstance(clone, (ast.FunctionDef, ast.AsyncFunctionDef)):
        raise TypeError("Expected a function node")
    clone.decorator_list = []
    clone.name = function_name or clone.name
    clone.returns = None
    clone.args.args[0].annotation = None
    clone.body = [ast.Return(value=ast.Name(id=arg, ctx=ast.Load()))]
    return ast.unparse(ast.fix_missing_locations(clone))


def _doc_expr(node: ast.AST) -> bool:
    return isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
