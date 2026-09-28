"""Reject function stubs introduced by a synthesized sandbox patch."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any


def inspect_generated_function_stubs(
    *, original_project: Path, sandbox_project: Path, patch: dict[str, Any]
) -> dict[str, Any]:
    paths = sorted({
        str(row.get("file") or row.get("path") or "").replace("\\", "/")
        for row in patch.get("patches") or []
        if isinstance(row, dict) and str(row.get("file") or row.get("path") or "").endswith(".py")
    })
    violations: list[dict[str, Any]] = []
    parse_failures: list[dict[str, str]] = []
    for relative in paths:
        original_nodes, original_error = _function_nodes(original_project / relative)
        sandbox_nodes, sandbox_error = _function_nodes(sandbox_project / relative)
        if original_error:
            parse_failures.append({"file": relative, "side": "original", "error": original_error})
        if sandbox_error:
            parse_failures.append({"file": relative, "side": "sandbox", "error": sandbox_error})
        if original_error or sandbox_error:
            continue
        for qualified_name, node in sandbox_nodes.items():
            marker = _stub_marker(node)
            if not marker:
                continue
            previous = original_nodes.get(qualified_name)
            if previous is not None and _stub_marker(previous):
                continue
            violations.append({
                "file": relative,
                "qualified_name": qualified_name,
                "line": node.lineno,
                "marker": marker,
                "change": "new_function_stub" if previous is None else "function_replaced_with_stub",
            })
    passed = not violations and not parse_failures
    return {
        "artifact_type": "GeneratedFunctionStubAdmission",
        "status": "passed" if passed else "blocked",
        "checked_files": paths,
        "violations": violations,
        "parse_failures": parse_failures,
        "policy": {
            "new_function_stubs_allowed": False,
            "existing_functions_may_be_replaced_with_stubs": False,
            "pre_existing_stubs_are_violations": False,
        },
    }


def _function_nodes(path: Path) -> tuple[dict[str, ast.FunctionDef | ast.AsyncFunctionDef], str | None]:
    if not path.is_file():
        return {}, None
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeError, SyntaxError) as exc:
        return {}, f"{type(exc).__name__}: {exc}"
    found: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}

    def visit(body: list[ast.stmt], prefix: tuple[str, ...] = ()) -> None:
        for node in body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                qualified = ".".join((*prefix, node.name))
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    found[qualified] = node
                visit(node.body, (*prefix, node.name))

    visit(tree.body)
    return found, None


def _stub_marker(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    body = list(node.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        body = body[1:]
    if len(body) != 1:
        return None
    statement = body[0]
    if isinstance(statement, ast.Pass):
        return "pass"
    if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant) and statement.value.value is Ellipsis:
        return "ellipsis"
    if isinstance(statement, ast.Raise) and _is_not_implemented_error(statement.exc):
        return "raise_not_implemented_error"
    if isinstance(statement, ast.Return) and isinstance(statement.value, ast.Name) and statement.value.id == "NotImplemented":
        return "return_not_implemented"
    return None


def _is_not_implemented_error(value: ast.expr | None) -> bool:
    if isinstance(value, ast.Name):
        return value.id == "NotImplementedError"
    return isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == "NotImplementedError"
