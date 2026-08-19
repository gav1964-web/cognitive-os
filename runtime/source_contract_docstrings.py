"""Extract callable contract shapes from common docstring formats."""

from __future__ import annotations

import re


def docstring_argument_types(snippet: str, names: list[str]) -> dict[str, str]:
    hints: dict[str, str] = {}
    for name in filter(None, names):
        patterns = (
            rf"(?m)^\s*{re.escape(name)}\s*:\s*([^\n]+)$",
            rf"(?m)^\s*{re.escape(name)}\s*\(([^)]+)\)\s*:",
        )
        for pattern in patterns:
            if match := re.search(pattern, snippet):
                hints[name] = match.group(1).strip()
                break
    return hints


def documented_output_shape(snippet: str) -> str:
    match = re.search(r"(?is)\breturns?\s*:?\s*\n\s*-*\s*\n?\s*([A-Za-z_][A-Za-z0-9_.\[\], :]+)", snippet)
    if not match:
        return ""
    documented = match.group(1).strip().rstrip(".")
    if ":" in documented:
        documented = documented.split(":", 1)[1].strip()
    lowered = documented.lower()
    families = (
        (("array", "matrix"), "ArrayLike"),
        (("tuple",), "TupleLike"),
        (("dict", "mapping"), "MappingLike"),
        (("list", "sequence"), "SequenceLike"),
    )
    for tokens, shape in families:
        if any(token in lowered for token in tokens):
            return shape
    return "str" if lowered in {"str", "string"} else documented
