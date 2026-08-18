"""AST-gated whole-function replacements for L4.5 sandbox candidates."""

from __future__ import annotations

import ast
import textwrap
from typing import Any


def replacement_shape_errors(replacement: str, target: str, source_excerpt: str) -> list[str]:
    if not replacement.strip():
        return ["missing_replacement_source"]
    current, current_error = _single_function(source_excerpt)
    proposed, proposed_error = _single_function(replacement)
    errors = [error for error in (current_error, proposed_error) if error]
    if errors or current is None or proposed is None:
        return errors
    expected_name = target.partition(":")[2].split(".")[-1]
    if proposed.name != expected_name:
        errors.append("replacement_target_name_mismatch")
    if type(proposed) is not type(current):
        errors.append("replacement_async_kind_mismatch")
    if ast.dump(proposed.args, include_attributes=False) != ast.dump(current.args, include_attributes=False):
        errors.append("replacement_signature_mismatch")
    if proposed.decorator_list:
        errors.append("replacement_decorators_forbidden")
    return errors


def apply_structured_replacement(original: str, target: str, replacement: str) -> tuple[str | None, str]:
    try:
        tree = ast.parse(original)
    except SyntaxError:
        return None, "target_file_syntax_error"
    qualified_symbol = target.partition(":")[2]
    matches = _qualified_function_matches(tree, qualified_symbol)
    if len(matches) != 1:
        return None, "structured_target_not_unique"
    node = matches[0]
    current = ast.get_source_segment(original, node) or ""
    errors = replacement_shape_errors(replacement, target, current)
    if errors:
        return None, errors[0]
    lines = original.splitlines()
    indent = lines[node.lineno - 1][: len(lines[node.lineno - 1]) - len(lines[node.lineno - 1].lstrip())]
    replacement_lines = textwrap.dedent(replacement).strip().splitlines()
    indented = [f"{indent}{line}" if line else "" for line in replacement_lines]
    patched_lines = [*lines[: node.lineno - 1], *indented, *lines[node.end_lineno or node.lineno :]]
    patched = "\n".join(patched_lines) + ("\n" if original.endswith("\n") else "")
    try:
        ast.parse(patched)
    except SyntaxError:
        return None, "structured_replacement_syntax_error"
    return patched, "structured_function_replacement_applied"


def _single_function(source: str) -> tuple[ast.FunctionDef | ast.AsyncFunctionDef | None, str]:
    try:
        tree = ast.parse(textwrap.dedent(source).strip())
    except SyntaxError:
        return None, "replacement_source_syntax_error"
    if len(tree.body) != 1 or not isinstance(tree.body[0], (ast.FunctionDef, ast.AsyncFunctionDef)):
        return None, "replacement_must_be_single_function"
    return tree.body[0], ""


def _qualified_function_matches(
    tree: ast.AST, qualified_symbol: str
) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    matches: list[ast.FunctionDef | ast.AsyncFunctionDef] = []

    class QualifiedVisitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.path: list[str] = []

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            self.path.append(node.name)
            self.generic_visit(node)
            self.path.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self._visit_function(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self._visit_function(node)

        def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
            self.path.append(node.name)
            path = ".".join(self.path)
            if path == qualified_symbol or ("." not in qualified_symbol and node.name == qualified_symbol):
                matches.append(node)
            self.generic_visit(node)
            self.path.pop()

    QualifiedVisitor().visit(tree)
    return matches
