"""Resolve bounded Python callable targets for Programmer components."""

from __future__ import annotations

import ast


FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


def qualified_function_matches(tree: ast.AST, qualified_symbol: str) -> list[FunctionNode]:
    matches: list[FunctionNode] = []

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

        def _visit_function(self, node: FunctionNode) -> None:
            self.path.append(node.name)
            path = ".".join(self.path)
            if path == qualified_symbol or ("." not in qualified_symbol and node.name == qualified_symbol):
                matches.append(node)
            self.generic_visit(node)
            self.path.pop()

    QualifiedVisitor().visit(tree)
    return matches
