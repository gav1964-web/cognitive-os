"""AST reducers for development-helper extraction patch synthesis."""

from __future__ import annotations

import ast
from typing import Any

from .python_parser_compatibility import parse_compatible_source

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

def _extract_json_dumps_helper(
    source: str,
    *,
    origin_symbol: str,
    proposed_symbol: str,
    maximum_free_variables: int,
) -> dict[str, Any] | None:
    try:
        tree, _ = parse_compatible_source(source, "<recovery-patch-source>")
    except SyntaxError:
        return None
    origin = _find_top_level_function(tree, origin_symbol)
    if origin is None or _find_top_level_function(tree, proposed_symbol) is not None:
        return None
    parents = _parent_map(origin)
    candidates: list[tuple[ast.Call, str]] = []
    for call in ast.walk(origin):
        if not isinstance(call, ast.Call) or _call_name(call.func) != "json.dumps" or len(call.args) != 1:
            continue
        writer = parents.get(call)
        if not (
            isinstance(writer, ast.Call)
            and isinstance(writer.func, ast.Attribute)
            and writer.func.attr == "write_text"
            and call in writer.args
        ):
            continue
        argument = call.args[0]
        loaded = sorted({
            node.id
            for node in ast.walk(argument)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
        })
        if len(loaded) != 1 or len(loaded) > maximum_free_variables:
            continue
        candidates.append((call, loaded[0]))
    if len(candidates) != 1:
        return None
    call, free_variable = candidates[0]
    segment = ast.get_source_segment(source, call)
    if not segment or source.count(segment) != 1:
        return None
    replaced = source.replace(segment, f"{proposed_symbol}({free_variable})", 1)
    helper_expression = ast.unparse(call)
    newline = "\r\n" if "\r\n" in source else "\n"
    helper = newline.join((
        f"def {proposed_symbol}({free_variable}):",
        f"    return {helper_expression}",
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
        "free_variable": free_variable,
        "serialization_line": int(getattr(call, "lineno", 0) or 0),
    }

def _extract_json_loads_helper(
    source: str,
    *,
    origin_symbol: str,
    proposed_symbol: str,
) -> dict[str, Any] | None:
    try:
        tree, _ = parse_compatible_source(source, "<recovery-patch-source>")
    except SyntaxError:
        return None
    origin = _find_top_level_function(tree, origin_symbol)
    if origin is None or _find_top_level_function(tree, proposed_symbol) is not None:
        return None
    candidates: list[tuple[ast.Call, ast.Call]] = []
    for call in ast.walk(origin):
        if not (
            isinstance(call, ast.Call)
            and _call_name(call.func) == "json.loads"
            and len(call.args) == 1
            and not call.keywords
            and isinstance(call.args[0], ast.Call)
            and _call_name(call.args[0].func).endswith("read_text")
        ):
            continue
        candidates.append((call, call.args[0]))
    if len(candidates) != 1:
        return None
    call, read_call = candidates[0]
    segment = ast.get_source_segment(source, call)
    read_expression = ast.get_source_segment(source, read_call)
    if not segment or not read_expression or source.count(segment) != 1:
        return None
    replaced = source.replace(segment, f"{proposed_symbol}({read_expression})", 1)
    newline = "\r\n" if "\r\n" in source else "\n"
    helper = newline.join((
        f"def {proposed_symbol}(text):",
        "    return json.loads(text)",
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
        "read_expression": read_expression,
        "parse_line": int(getattr(call, "lineno", 0) or 0),
    }

def _extract_splitlines_helper(
    source: str,
    *,
    origin_symbol: str,
    proposed_symbol: str,
) -> dict[str, Any] | None:
    try:
        tree, _ = parse_compatible_source(source, "<recovery-patch-source>")
    except SyntaxError:
        return None
    origin = _find_top_level_function(tree, origin_symbol)
    if origin is None or _find_top_level_function(tree, proposed_symbol) is not None:
        return None
    candidates = [
        call for call in ast.walk(origin)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and call.func.attr == "splitlines"
        and not call.args
        and not call.keywords
    ]
    if len(candidates) != 1:
        return None
    call = candidates[0]
    text_expression = ast.get_source_segment(source, call.func.value)
    segment = ast.get_source_segment(source, call)
    if not text_expression or not segment or source.count(segment) != 1:
        return None
    replaced = source.replace(segment, f"{proposed_symbol}({text_expression})", 1)
    newline = "\r\n" if "\r\n" in source else "\n"
    helper = newline.join((
        f"def {proposed_symbol}(text):",
        "    return text.splitlines()",
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
        "text_expression": text_expression,
        "split_line": int(getattr(call, "lineno", 0) or 0),
    }

def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""

def _parent_map(node: ast.AST) -> dict[ast.AST, ast.AST]:
    return {child: parent for parent in ast.walk(node) for child in ast.iter_child_nodes(parent)}

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

def _find_top_level_function(tree: ast.Module, function_name: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    return next(
        (
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name
        ),
        None,
    )
