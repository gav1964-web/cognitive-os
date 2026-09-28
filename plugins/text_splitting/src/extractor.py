"""Source-only splitlines helper extraction; preserved legacy algorithm."""
import ast
from typing import Any

from cognitive_inspect.python_parser_compatibility import parse_compatible_source
from cognitive_inspect.ast_navigation import find_top_level_function as _find_top_level_function


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

