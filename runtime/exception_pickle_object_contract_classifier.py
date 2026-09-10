from __future__ import annotations

import ast
from typing import Any

from .exception_pickle_autonomous_shadow import _sample_constructor_value

SAFE_ZERO_ARG_METHOD_RETURNS = {
    "json": "mapping",
    "read": "string",
    "text": "string",
    "decode": "string",
}


def unsupported_constructor_parameters(row: dict[str, Any]) -> list[str]:
    return [
        name
        for name in [str(value) for value in row.get("required_constructor_parameters") or []]
        if name and _sample_constructor_value(name) is None
    ]


def classify_parameter(*, source: str, init_node: ast.FunctionDef, parameter: str) -> dict[str, Any]:
    visitor = ParameterUseVisitor(parameter)
    visitor.visit(init_node)
    kind, strategy, confidence = _classification(visitor)
    return {
        "parameter": parameter,
        "contract_kind": kind,
        "sample_strategy": strategy,
        "confidence": confidence,
        "evidence": {
            "attributes": sorted(visitor.attributes),
            "mapping_keys": sorted(visitor.mapping_keys | visitor.mapping_get_keys),
            "rendered": visitor.rendered,
            "iterated": visitor.iterated,
            "joined": visitor.joined,
            "method_calls": sorted(visitor.method_calls),
            "method_call_arg_counts": dict(sorted(visitor.method_call_arg_counts.items())),
            "method_return_profiles": {
                method: SAFE_ZERO_ARG_METHOD_RETURNS[method]
                for method in sorted(visitor.method_calls)
                if method in SAFE_ZERO_ARG_METHOD_RETURNS
            },
            "assignments": sorted(visitor.assignments),
            "aliases": sorted(visitor.aliases - {visitor.parameter}),
            "line_numbers": sorted(visitor.line_numbers),
            "opaque_reasons": opaque_reasons(visitor),
        },
        "source_backed": True,
        "promotion_allowed": False,
    }


def _classification(visitor: "ParameterUseVisitor") -> tuple[str, str, float]:
    if visitor.method_calls:
        if safe_method_contract(visitor):
            return "method_object", "method-backed sample with bounded zero-arg return values", 0.76
        return "opaque_hold", "hold until method-call behavior is source-backed", 0.55
    if visitor.mapping_keys or visitor.mapping_get_keys:
        return "mapping_object", "dict sample with observed literal keys", 0.82
    if visitor.attributes:
        return "attribute_object", "SimpleNamespace sample with observed attributes", 0.8
    if visitor.iterated or visitor.joined:
        return "iterable_string_list", "single-element string list", 0.74
    if visitor.rendered or visitor.string_ops:
        return "string_like", "source-backed string sample", 0.72
    if visitor.raised_or_chained:
        return "exception_like", "RuntimeError sample preserving message", 0.68
    return "opaque_hold", "hold until source-backed object contract exists", 0.5


def opaque_reasons(visitor: "ParameterUseVisitor") -> list[str]:
    reasons = []
    if visitor.method_calls and not safe_method_contract(visitor):
        reasons.append("parameter_method_call")
    if not any((
        visitor.attributes,
        visitor.mapping_keys,
        visitor.mapping_get_keys,
        visitor.rendered,
        visitor.iterated,
        visitor.joined,
        visitor.string_ops,
        visitor.raised_or_chained,
    )):
        reasons.append("no_supported_usage_evidence")
    return reasons


def safe_method_contract(visitor: "ParameterUseVisitor") -> bool:
    if not visitor.method_calls:
        return False
    if not visitor.method_calls <= set(SAFE_ZERO_ARG_METHOD_RETURNS):
        return False
    return all(count == 0 for count in visitor.method_call_arg_counts.values())


class ParameterUseVisitor(ast.NodeVisitor):
    def __init__(self, parameter: str) -> None:
        self.parameter = parameter
        self.aliases: set[str] = {parameter}
        self.attributes: set[str] = set()
        self.mapping_keys: set[str] = set()
        self.mapping_get_keys: set[str] = set()
        self.method_calls: set[str] = set()
        self.method_call_arg_counts: dict[str, int] = {}
        self.assignments: set[str] = set()
        self.line_numbers: set[int] = set()
        self.rendered = False
        self.iterated = False
        self.joined = False
        self.string_ops = False
        self.raised_or_chained = False

    def visit_Attribute(self, node: ast.Attribute) -> Any:
        if self._is_reference(node.value):
            self.attributes.add(node.attr)
            self.line_numbers.add(getattr(node, "lineno", 0))
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> Any:
        if self._is_reference(node.value):
            key = literal_string(node.slice)
            if key:
                self.mapping_keys.add(key)
            self.line_numbers.add(getattr(node, "lineno", 0))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> Any:
        if isinstance(node.func, ast.Attribute) and self._is_reference(node.func.value):
            if node.func.attr == "get":
                key = literal_string(node.args[0]) if node.args else ""
                if key:
                    self.mapping_get_keys.add(key)
            else:
                self.method_calls.add(node.func.attr)
                self.method_call_arg_counts[node.func.attr] = max(
                    self.method_call_arg_counts.get(node.func.attr, 0),
                    len(node.args) + len(node.keywords),
                )
            self.line_numbers.add(getattr(node, "lineno", 0))
        if is_join_call(node) and any(self._contains_reference(arg) for arg in node.args):
            self.joined = True
            self.line_numbers.add(getattr(node, "lineno", 0))
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> Any:
        if self._contains_reference(node.iter):
            self.iterated = True
            self.line_numbers.add(getattr(node, "lineno", 0))
        self.generic_visit(node)

    def visit_JoinedStr(self, node: ast.JoinedStr) -> Any:
        if any(self._contains_reference(value) for value in node.values):
            self.rendered = True
            self.line_numbers.add(getattr(node, "lineno", 0))
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> Any:
        if isinstance(node.op, (ast.Add, ast.Mod)) and self._contains_reference(node):
            self.string_ops = True
            self.line_numbers.add(getattr(node, "lineno", 0))
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> Any:
        if self._contains_reference(node.value):
            for target in node.targets:
                name = assignment_name(target)
                if name:
                    self.assignments.add(name)
                    if isinstance(target, ast.Name):
                        self.aliases.add(name)
            self.line_numbers.add(getattr(node, "lineno", 0))
        self.generic_visit(node)

    def visit_Raise(self, node: ast.Raise) -> Any:
        if self._contains_reference(node):
            self.raised_or_chained = True
            self.line_numbers.add(getattr(node, "lineno", 0))
        self.generic_visit(node)

    def _is_reference(self, node: ast.AST) -> bool:
        return isinstance(node, ast.Name) and node.id in self.aliases

    def _contains_reference(self, node: ast.AST) -> bool:
        return any(isinstance(child, ast.Name) and child.id in self.aliases for child in ast.walk(node))


def literal_string(node: ast.AST) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return ""


def is_join_call(node: ast.Call) -> bool:
    return isinstance(node.func, ast.Attribute) and node.func.attr == "join"


def assignment_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""
