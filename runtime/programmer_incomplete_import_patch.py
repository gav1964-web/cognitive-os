"""Bounded AST edit for incomplete import token parsing."""

from __future__ import annotations

import ast
from typing import Any


def incomplete_import_token_patch(
    source: str, *, symbol: str, recipe: dict[str, Any]
) -> dict[str, Any] | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    function = next(
        (node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == symbol),
        None,
    )
    if function is None or symbol != str(recipe.get("required_symbol") or ""):
        return None
    index = int(recipe.get("required_token_index") or -1)
    candidates = [node for node in ast.walk(function) if _split_index_assignment(node, index)]
    if len(candidates) != 1:
        return None
    assignment = candidates[0]
    assert isinstance(assignment, ast.Assign)
    assert isinstance(assignment.targets[0], ast.Name)
    assert isinstance(assignment.value, ast.Subscript)
    call = assignment.value.value
    assert isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
    assert isinstance(call.func.value, ast.Name)
    source_parameter = call.func.value.id
    indexed_token = assignment.targets[0].id
    parameters = {arg.arg for arg in [*function.args.posonlyargs, *function.args.args]}
    if source_parameter not in parameters:
        return None

    clone = ast.parse(ast.unparse(function)).body[0]
    assert isinstance(clone, ast.FunctionDef)
    clone_assignment = next(
        (node for node in ast.walk(clone) if _split_index_assignment(node, index)),
        None,
    )
    if not isinstance(clone_assignment, ast.Assign):
        return None
    container = next(
        (node.body for node in ast.walk(clone) if hasattr(node, "body") and isinstance(node.body, list) and clone_assignment in node.body),
        None,
    )
    if container is None:
        return None
    parts_name = "parts"
    if parts_name in {node.id for node in ast.walk(clone) if isinstance(node, ast.Name)}:
        return None
    replacement = ast.parse(
        f"{parts_name} = {source_parameter}.split()\n"
        f"if len({parts_name}) < {index + 1}:\n"
        "    return None\n"
        f"{indexed_token} = {parts_name}[{index}]\n"
    ).body
    position = container.index(clone_assignment)
    container[position:position + 1] = replacement
    rendered = ast.unparse(ast.fix_missing_locations(clone))
    lines = source.splitlines(keepends=True)
    start = int(function.lineno) - 1
    end = int(getattr(function, "end_lineno", function.lineno))
    newline = "\r\n" if "\r\n" in source else "\n"
    patched = "".join(lines[:start]) + rendered.replace("\n", newline) + newline + "".join(lines[end:])
    try:
        ast.parse(patched)
    except SyntaxError:
        return None
    return {
        "source": patched,
        "source_parameter": source_parameter,
        "indexed_token": indexed_token,
    }


def _split_index_assignment(node: ast.AST, index: int) -> bool:
    if not (
        isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and isinstance(node.value, ast.Subscript)
        and isinstance(node.value.value, ast.Call)
        and isinstance(node.value.value.func, ast.Attribute)
        and node.value.value.func.attr == "split"
        and isinstance(node.value.value.func.value, ast.Name)
        and not node.value.value.args
        and not node.value.value.keywords
    ):
        return False
    slice_node = node.value.slice
    return isinstance(slice_node, ast.Constant) and slice_node.value == index
