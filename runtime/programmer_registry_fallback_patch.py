"""Bounded AST edit for a missing Windows registry value fallback."""

from __future__ import annotations

import ast
from typing import Any


def registry_env_fallback_patch(
    source: str,
    *,
    symbol: str,
    recipe: dict[str, Any],
) -> dict[str, Any] | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    function = next(
        (node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == symbol),
        None,
    )
    fallback_name = str(recipe.get("fallback_function") or "")
    exception_name = str(recipe.get("required_exception") or "")
    call_attribute = str(recipe.get("required_call_attribute") or "")
    fallback = next(
        (node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == fallback_name),
        None,
    )
    if function is None or fallback is None or not exception_name or not call_attribute:
        return None
    positional = [*function.args.posonlyargs, *function.args.args]
    if len(positional) != 1 or function.args.vararg or function.args.kwarg:
        return None
    candidate_with = next(
        (
            statement for statement in function.body
            if isinstance(statement, ast.With)
            and any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == call_attribute
                for node in ast.walk(statement)
            )
        ),
        None,
    )
    if candidate_with is None:
        return None
    clone = ast.parse(ast.unparse(function)).body[0]
    assert isinstance(clone, ast.FunctionDef)
    clone_with = next(
        (
            statement for statement in clone.body
            if isinstance(statement, ast.With)
            and any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == call_attribute
                for node in ast.walk(statement)
            )
        ),
        None,
    )
    if clone_with is None:
        return None
    fallback_return = ast.Return(
        value=ast.Call(
            func=ast.Name(id=fallback_name, ctx=ast.Load()),
            args=[ast.Name(id=positional[0].arg, ctx=ast.Load())],
            keywords=[],
        )
    )
    wrapped = ast.Try(
        body=[clone_with],
        handlers=[ast.ExceptHandler(
            type=ast.Name(id=exception_name, ctx=ast.Load()),
            name=None,
            body=[fallback_return],
        )],
        orelse=[],
        finalbody=[],
    )
    clone.body[clone.body.index(clone_with)] = wrapped
    replacement = ast.unparse(ast.fix_missing_locations(clone))
    lines = source.splitlines(keepends=True)
    start = int(function.lineno) - 1
    end = int(getattr(function, "end_lineno", function.lineno))
    newline = "\r\n" if "\r\n" in source else "\n"
    patched = "".join(lines[:start]) + replacement.replace("\n", newline) + newline + "".join(lines[end:])
    try:
        ast.parse(patched)
    except SyntaxError:
        return None
    return {
        "source": patched,
        "exception": exception_name,
        "fallback_function": fallback_name,
        "guarded_call_attribute": call_attribute,
    }
