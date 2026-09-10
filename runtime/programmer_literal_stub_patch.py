"""Literal-return stub patch recipe for Programmer Executor."""

from __future__ import annotations

import ast
from typing import Any


def literal_return_patch(
    source: str,
    function_name: str,
    target: str,
    path_text: str,
    test_plan: dict[str, Any],
    recipe: dict[str, Any],
) -> dict[str, Any] | None:
    value = _expected_literal(test_plan, target, recipe)
    if value is None:
        return None
    tree = ast.parse(source)
    function = _find_patchable_function(tree, function_name)
    if function is None or not _is_stub_function(function):
        return None
    literal = repr(value)
    if len(literal) > int(recipe.get("max_literal_repr_chars") or 200):
        return None
    lines = source.splitlines()
    indent = _body_indent(lines, function)
    start = function.body[0].lineno - 1
    end = function.body[-1].end_lineno or function.body[-1].lineno
    patched = lines[:start] + [f"{indent}return {literal}"] + lines[end:]
    return {
        "source": "\n".join(patched) + ("\n" if source.endswith("\n") else ""),
        "return_value": value,
        "return_evidence": {
            "source": "contract_return_literal_case",
            "expect_keys": recipe.get("expect_keys"),
            "target": target,
            "file": path_text,
        },
    }


def notimplemented_return_patch(
    source: str,
    function_name: str,
    target: str,
    path_text: str,
    test_plan: dict[str, Any],
    recipe: dict[str, Any],
) -> dict[str, Any] | None:
    value = _expected_literal(test_plan, target, recipe)
    if value is None:
        return None
    tree = ast.parse(source)
    function = _find_patchable_function(tree, function_name)
    if function is None or not _is_notimplemented_function(function):
        return None
    literal = repr(value)
    if len(literal) > int(recipe.get("max_literal_repr_chars") or 200):
        return None
    lines = source.splitlines()
    indent = _body_indent(lines, function)
    start = function.body[0].lineno - 1
    end = function.body[-1].end_lineno or function.body[-1].lineno
    patched = lines[:start] + [f"{indent}return {literal}"] + lines[end:]
    return {
        "source": "\n".join(patched) + ("\n" if source.endswith("\n") else ""),
        "return_value": value,
        "return_evidence": {
            "source": "contract_return_literal_notimplemented_case",
            "expect_keys": recipe.get("expect_keys"),
            "target": target,
            "file": path_text,
        },
    }


def _expected_literal(test_plan: dict[str, Any], target: str, recipe: dict[str, Any]) -> Any:
    positive_kind = str(recipe.get("positive_case_kind") or "positive_contract_case")
    keys = [str(item) for item in list(recipe.get("expect_keys") or [])]
    for row in list(dict(test_plan.get("executable_acceptance") or {}).get("obligations") or []):
        if not isinstance(row, dict) or row.get("target") != target or row.get("kind") != positive_kind:
            continue
        expect = row.get("expect")
        if not isinstance(expect, dict):
            continue
        for key in keys:
            if key in expect and _literal_is_safe(expect[key]):
                return expect[key]
    return None


def _literal_is_safe(value: Any) -> bool:
    if value is None or isinstance(value, (str, int, float, bool)):
        return True
    if isinstance(value, list):
        return all(_literal_is_safe(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and _literal_is_safe(item) for key, item in value.items())
    return False


def _is_stub_function(function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    body = [
        node
        for node in function.body
        if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str))
    ]
    if len(body) != 1:
        return False
    node = body[0]
    return isinstance(node, ast.Pass) or (isinstance(node, ast.Return) and node.value is None) or (
        isinstance(node, ast.Return) and isinstance(node.value, ast.Constant) and node.value.value is None
    )


def _is_notimplemented_function(function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    body = [
        node
        for node in function.body
        if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str))
    ]
    return len(body) == 1 and isinstance(body[0], ast.Raise) and _raises_notimplemented(body[0])


def _raises_notimplemented(node: ast.Raise) -> bool:
    exc = node.exc
    if isinstance(exc, ast.Name):
        return exc.id == "NotImplementedError"
    if isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name):
        return exc.func.id == "NotImplementedError"
    return False


def _find_patchable_function(tree: ast.Module, function_name: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name
    ]
    return matches[0] if len(matches) == 1 else None


def _body_indent(lines: list[str], function: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    if function.body:
        line = lines[function.body[0].lineno - 1]
        return line[: len(line) - len(line.lstrip())]
    line = lines[function.lineno - 1]
    return line[: len(line) - len(line.lstrip())] + "    "
