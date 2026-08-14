"""Compatibility parsing for Python syntax outside the host AST grammar."""

from __future__ import annotations

import ast
import re
import warnings


class ParserVersionIncompatible(SyntaxError):
    """The source is valid for a known Python grammar, but not the host parser."""

    def __init__(self, original: SyntaxError) -> None:
        super().__init__(*original.args)


def parse_compatible_source(source: str, filename: str) -> tuple[ast.AST, str | None]:
    try:
        return ast.parse(source, filename=filename), None
    except SyntaxError as error:
        if _newer_python_syntax(source, error):
            raise ParserVersionIncompatible(error) from error
        if not _looks_like_python2(source, error):
            raise
        converted = _convert_python2(source, filename)
        if converted is None:
            raise
        return ast.parse(converted, filename=filename), "python2_compatibility_ast"


def _newer_python_syntax(source: str, error: SyntaxError) -> bool:
    lines = source.splitlines()
    if not error.lineno or error.lineno > len(lines):
        return False
    line = lines[error.lineno - 1]
    return bool(
        re.match(r"^\s*(?:(?:async\s+)?def|class)\s+[A-Za-z_]\w*\s*\[", line)
        or re.match(r"^\s*type\s+[A-Za-z_]\w*(?:\s*\[.*\])?\s*=", line)
    )


def _looks_like_python2(source: str, error: SyntaxError) -> bool:
    lines = source.splitlines()
    line = lines[error.lineno - 1] if error.lineno and error.lineno <= len(lines) else ""
    return bool(
        re.search(r"python(?:2|\s+2(?:\.\d+)?)\b", source[:2000], re.IGNORECASE)
        or re.match(r"^\s*print(?:\s+|>>)(?!\s*\()", line)
        or re.match(r"^\s*except\s+[^:]+,\s*\w+\s*:", line)
        or re.match(r"^\s*raise\s+\w+\s*,", line)
        or re.search(r"<>|`[^`]+`", line)
    )


def _convert_python2(source: str, filename: str) -> str | None:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from lib2to3.refactor import RefactoringTool, get_fixers_from_package

            tool = RefactoringTool(get_fixers_from_package("lib2to3.fixes"))
            normalized = source if source.endswith("\n") else source + "\n"
            return str(tool.refactor_string(normalized, filename))
    except Exception:
        return None
