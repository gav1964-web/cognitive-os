"""Source-only JSON serialization helper extraction; preserved legacy algorithm."""
import ast
from typing import Any

from cognitive_inspect.python_parser_compatibility import parse_compatible_source
from cognitive_inspect.ast_navigation import parent_map as _parent_map, find_top_level_function as _find_top_level_function, call_name as _call_name


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

