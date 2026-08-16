"""Small AST helpers shared by source contract inference."""

from __future__ import annotations

import ast

from runtime.source_ast_scope import callable_scope_walk


def local_type_factories(function: ast.AST) -> dict[str, str]:
    return {
        node.name: "TypeFactory"
        for node in getattr(function, "body", [])
        if isinstance(node, ast.ClassDef)
    }


def target_mutates_external_state(target: ast.AST, local_names: set[str]) -> bool:
    if isinstance(target, ast.Attribute):
        return not isinstance(target.value, ast.Name) or target.value.id not in local_names
    if isinstance(target, ast.Subscript):
        return not isinstance(target.value, ast.Name) or target.value.id not in local_names
    return False


def xml_call_shape(name: str) -> str:
    if name.endswith(("element", "subelement")):
        return "XMLNodeLike"
    if name.endswith(("tostring", "tostringlist")):
        return "bytes"
    return ""


def yield_path_count(function: ast.AST | None) -> int:
    return sum(isinstance(node, (ast.Yield, ast.YieldFrom)) for node in callable_scope_walk(function)) if function else 0


def is_file_extension_policy(function: ast.AST | None) -> bool:
    if function is None:
        return False
    text = ast.unparse(function).lower()
    args = {arg.arg.lower() for arg in function.args.args}
    return bool(
        args & {"filename", "file_name", "name"}
        and ("rsplit" in text or "splitext" in text or ".suffix" in text)
        and "allowed" in text
        and (".lower()" in text or ".casefold()" in text)
        and any(isinstance(node, ast.Return) and isinstance(node.value, (ast.BoolOp, ast.Compare)) for node in callable_scope_walk(function))
    )


def binary_result_shape(operand_shapes: set[str]) -> str:
    if "str" in operand_shapes:
        return "str"
    return "ArrayLike" if "ArrayLike" in operand_shapes else "NumberLike"
