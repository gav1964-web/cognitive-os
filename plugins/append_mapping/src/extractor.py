"""Bounded append-mapping helper proposal; never applies source edits."""
from __future__ import annotations

import ast
from typing import Any

from cognitive_inspect.python_parser_compatibility import parse_compatible_source
from cognitive_inspect.ast_navigation import parent_map as _parent_map, find_top_level_function as _find_top_level_function


def _extract_append_mapping_helper(
    source: str,
    *,
    origin_symbol: str,
    proposed_symbol: str,
    maximum_mapping_fields: int,
) -> dict[str, Any] | None:
    try:
        tree, _ = parse_compatible_source(source, "<recovery-patch-source>")
    except SyntaxError:
        return None
    origin = _find_top_level_function(tree, origin_symbol)
    if origin is None or _find_top_level_function(tree, proposed_symbol) is not None:
        return None
    parents = _parent_map(origin)
    candidates = []
    for call in ast.walk(origin):
        if not (
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr == "append"
            and isinstance(call.func.value, ast.Name)
            and len(call.args) == 1
            and not call.keywords
        ):
            continue
        loop = _enclosing_loop(call, parents)
        if not isinstance(loop, ast.For) or not isinstance(loop.target, ast.Name):
            continue
        if _enclosing_loop(loop, parents) is not None:
            continue
        argument = call.args[0]
        mapping_source = "inline_append"
        if isinstance(argument, ast.Dict):
            mapping = argument
        elif isinstance(argument, ast.Name):
            expression = parents.get(call)
            if not isinstance(expression, ast.Expr) or expression not in loop.body:
                continue
            append_index = loop.body.index(expression)
            if append_index == 0:
                continue
            assignment = loop.body[append_index - 1]
            if not (
                isinstance(assignment, ast.Assign)
                and len(assignment.targets) == 1
                and isinstance(assignment.targets[0], ast.Name)
                and assignment.targets[0].id == argument.id
                and isinstance(assignment.value, ast.Dict)
            ):
                continue
            temporary_uses = [
                node for node in ast.walk(loop)
                if isinstance(node, ast.Name) and node.id == argument.id
            ]
            if (
                len(temporary_uses) != 2
                or sum(isinstance(node.ctx, ast.Store) for node in temporary_uses) != 1
                or sum(isinstance(node.ctx, ast.Load) for node in temporary_uses) != 1
            ):
                continue
            mapping = assignment.value
            mapping_source = "preceding_assignment"
        else:
            continue
        if len(mapping.keys) > maximum_mapping_fields:
            continue
        loop_variable = loop.target.id
        loaded = {
            node.id
            for node in ast.walk(mapping)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
        }
        if loaded != {loop_variable}:
            continue
        accumulator = call.func.value.id
        if not _returns_name(origin, accumulator):
            continue
        candidates.append((call, mapping, loop_variable, accumulator, mapping_source))
    if len(candidates) != 1:
        return None
    call, mapping, loop_variable, accumulator, mapping_source = candidates[0]
    segment = ast.get_source_segment(source, mapping)
    if not segment or source.count(segment) != 1:
        return None
    replacement = f"{proposed_symbol}({loop_variable})"
    replaced = source.replace(segment, replacement, 1)
    helper_mapping = ast.unparse(mapping)
    newline = "\r\n" if "\r\n" in source else "\n"
    helper = newline.join((
        f"def {proposed_symbol}({loop_variable}):",
        f"    return {helper_mapping}",
        "",
        "",
    ))
    lines = replaced.splitlines(keepends=True)
    insert_at = max(0, origin.lineno - 1)
    patched = "".join(lines[:insert_at]) + helper + "".join(lines[insert_at:])
    if source.endswith(("\n", "\r")) and not patched.endswith(("\n", "\r")):
        patched += newline
    return {
        "source": patched,
        "loop_variable": loop_variable,
        "accumulator": accumulator,
        "mapping_field_count": len(mapping.keys),
        "mapping_source": mapping_source,
        "append_line": int(getattr(call, "lineno", 0) or 0),
    }



def _enclosing_loop(
    node: ast.AST,
    parents: dict[ast.AST, ast.AST],
) -> ast.For | ast.AsyncFor | None:
    current = node
    while current in parents:
        current = parents[current]
        if isinstance(current, (ast.For, ast.AsyncFor)):
            return current
    return None



def _returns_name(function: ast.FunctionDef | ast.AsyncFunctionDef, name: str) -> bool:
    returns = [node for node in ast.walk(function) if isinstance(node, ast.Return)]
    return len(returns) == 1 and isinstance(returns[0].value, ast.Name) and returns[0].value.id == name

