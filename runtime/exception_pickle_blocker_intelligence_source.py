"""Source-code fact extraction for exception-pickle blocker intelligence."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any


def _source_facts(root: Path, row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {"available": False, "fact_tags": ["audit_row_missing"]}
    source_path = root / str(row.get("project_root") or "") / str(row.get("path") or "")
    try:
        source = source_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        source = source_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"available": False, "fact_tags": ["source_missing"]}
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {"available": False, "fact_tags": ["source_parse_failed"]}
    class_node = _find_class(tree, str(row.get("class_name") or ""))
    init_node = _find_init(tree, str(row.get("class_name") or ""))
    if init_node is None:
        return {"available": False, "fact_tags": ["init_missing"]}
    required = [str(value) for value in row.get("required_constructor_parameters") or []]
    visitor = _InitFactVisitor(set(required))
    visitor.visit(init_node)
    tags = set(visitor.fact_tags)
    if _has_attribute_base_class_definition(tree):
        tags.add("attribute_base_class_definition")
    class_attrs = _class_attribute_names(class_node)
    missing_self_reads = sorted(
        set(visitor.self_attribute_reads) - set(visitor.self_assignments) - class_attrs
    )
    if missing_self_reads:
        tags.add("target_self_attribute_read_without_assignment")
    if bool(row.get("formatted_super_argument")):
        tags.add("base_exception_argument_transform")
    return {
        "available": True,
        "fact_tags": sorted(tags),
        "self_assignments": dict(sorted(visitor.self_assignments.items())),
        "self_attribute_reads": sorted(set(visitor.self_attribute_reads)),
        "missing_self_attribute_reads": missing_self_reads,
        "class_attributes": sorted(class_attrs),
        "method_calls": dict(sorted(visitor.method_calls.items())),
        "attribute_accesses": dict(sorted(visitor.attribute_accesses.items())),
        "mapping_accesses": dict(sorted(visitor.mapping_accesses.items())),
        "line_numbers": sorted(visitor.line_numbers),
    }


class _InitFactVisitor(ast.NodeVisitor):
    def __init__(self, parameters: set[str]) -> None:
        self.parameters = parameters
        self.fact_tags: set[str] = set()
        self.self_assignments: dict[str, list[str]] = {}
        self.self_attribute_reads: list[str] = []
        self.method_calls: dict[str, list[str]] = {}
        self.attribute_accesses: dict[str, list[str]] = {}
        self.mapping_accesses: dict[str, list[str]] = {}
        self.line_numbers: set[int] = set()

    def visit_Assign(self, node: ast.Assign) -> Any:
        refs = _referenced_parameters(node.value, self.parameters)
        for target in node.targets:
            attr = _self_attr_name(target)
            if attr and refs:
                self.self_assignments[attr] = sorted(refs)
                self.fact_tags.add("direct_self_assignment" if _is_plain_name(node.value, refs) else "derived_self_assignment")
                self.line_numbers.add(getattr(node, "lineno", 0))
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> Any:
        if isinstance(node.value, ast.Name) and node.value.id in self.parameters:
            self.attribute_accesses.setdefault(node.value.id, []).append(node.attr)
            self.fact_tags.add("attribute_access")
            self.line_numbers.add(getattr(node, "lineno", 0))
        if (
            isinstance(node.value, ast.Name)
            and node.value.id == "self"
            and isinstance(node.ctx, ast.Load)
            and node.attr != "__class__"
        ):
            self.self_attribute_reads.append(node.attr)
            self.line_numbers.add(getattr(node, "lineno", 0))
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> Any:
        if isinstance(node.value, ast.Name) and node.value.id in self.parameters:
            self.mapping_accesses.setdefault(node.value.id, []).append(_slice_text(node.slice))
            self.fact_tags.add("mapping_access")
            self.line_numbers.add(getattr(node, "lineno", 0))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> Any:
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id in self.parameters:
                self.method_calls.setdefault(node.func.value.id, []).append(node.func.attr)
                self.fact_tags.add("parameter_method_call")
                self.line_numbers.add(getattr(node, "lineno", 0))
            if node.func.attr in {"join", "format"} and _referenced_parameters(node, self.parameters):
                self.fact_tags.add("string_rendering")
                self.line_numbers.add(getattr(node, "lineno", 0))
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> Any:
        if _referenced_parameters(node.iter, self.parameters):
            self.fact_tags.add("iterable_usage")
            self.line_numbers.add(getattr(node, "lineno", 0))
        self.generic_visit(node)

    def visit_JoinedStr(self, node: ast.JoinedStr) -> Any:
        if _referenced_parameters(node, self.parameters):
            self.fact_tags.add("string_rendering")
            self.line_numbers.add(getattr(node, "lineno", 0))
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> Any:
        if isinstance(node.op, (ast.Add, ast.Mod)) and _referenced_parameters(node, self.parameters):
            self.fact_tags.add("string_rendering")
            self.line_numbers.add(getattr(node, "lineno", 0))
        self.generic_visit(node)


def _find_init(tree: ast.AST, class_name: str) -> ast.FunctionDef | None:
    class_node = _find_class(tree, class_name)
    if class_node is None:
        return None
    for child in class_node.body:
        if isinstance(child, ast.FunctionDef) and child.name == "__init__":
            return child
    return None


def _find_class(tree: ast.AST, class_name: str) -> ast.ClassDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return node
    return None


def _class_attribute_names(class_node: ast.ClassDef | None) -> set[str]:
    if class_node is None:
        return set()
    attrs: set[str] = set()
    for child in class_node.body:
        if isinstance(child, ast.Assign):
            for target in child.targets:
                if isinstance(target, ast.Name):
                    attrs.add(target.id)
        elif (
            isinstance(child, ast.AnnAssign)
            and isinstance(child.target, ast.Name)
            and child.value is not None
        ):
            attrs.add(child.target.id)
    return attrs


def _has_attribute_base_class_definition(tree: ast.AST) -> bool:
    return any(
        isinstance(node, ast.ClassDef)
        and any(isinstance(base, ast.Attribute) for base in node.bases)
        for node in ast.walk(tree)
    )


def _referenced_parameters(node: ast.AST, parameters: set[str]) -> set[str]:
    return {
        child.id
        for child in ast.walk(node)
        if isinstance(child, ast.Name) and child.id in parameters
    }


def _is_plain_name(node: ast.AST, refs: set[str]) -> bool:
    return isinstance(node, ast.Name) and node.id in refs


def _self_attr_name(node: ast.AST) -> str:
    if (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    ):
        return node.attr
    return ""


def _slice_text(node: ast.AST) -> str:
    if isinstance(node, ast.Constant):
        return repr(node.value)
    try:
        return ast.unparse(node)
    except Exception:
        return type(node).__name__
