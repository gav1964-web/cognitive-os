"""Infer local expression result shapes for source contracts."""

from __future__ import annotations

import ast

from runtime.source_ast_scope import callable_scope_walk
from runtime.source_contract_helpers import binary_result_shape, xml_call_shape
from runtime.source_dispatch_evidence import is_receiver_request_dispatch


ARRAY_PREFIXES = ("torch.", "tf.", "tensorflow.", "np.", "numpy.")
ARRAY_CALL_SUFFIXES = (
    "sum", "mean", "clamp", "sqrt", "square", "exp", "log", "log1p", "log10", "log2",
)


def assignment_shapes(function: ast.AST, initial: dict[str, str] | None = None) -> dict[str, str]:
    shapes = dict(initial or {})
    for node in callable_scope_walk(function):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        shape = expression_shape(value, shapes) if value is not None else ""
        for target in targets:
            if isinstance(target, ast.Name) and shape:
                shapes[target.id] = shape
            elif isinstance(target, (ast.Tuple, ast.List)) and isinstance(value, ast.Name):
                item_shape = "ArrayLike" if shapes.get(value.id) == "ArrayLike" else "ItemLike"
                shapes.update({item.id: item_shape for item in target.elts if isinstance(item, ast.Name)})
            elif isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name):
                shapes[target.value.id] = "MappingLike"
    return shapes


def expression_shape(node: ast.AST, assignments: dict[str, str]) -> str:
    literals = {ast.Dict: "MappingLike", ast.List: "SequenceLike", ast.ListComp: "SequenceLike", ast.Tuple: "TupleLike", ast.Set: "SetLike"}
    if type(node) in literals:
        return literals[type(node)]
    if isinstance(node, ast.Name):
        return "ReceiverState" if node.id in {"self", "cls"} else assignments.get(node.id, "")
    if isinstance(node, ast.IfExp):
        shapes = {expression_shape(branch, assignments) for branch in (node.body, node.orelse)} - {""}
        ordered = sorted(shapes)
        return ordered[0] if len(ordered) == 1 else f"Union[{', '.join(ordered)}]" if ordered else ""
    if isinstance(node, (ast.BoolOp, ast.Compare)):
        return "bool"
    if isinstance(node, ast.Await):
        return expression_shape(node.value, assignments)
    if isinstance(node, ast.Constant):
        return type(node.value).__name__
    if isinstance(node, ast.Attribute):
        return "AttributeValue"
    if isinstance(node, ast.BinOp):
        return binary_result_shape({expression_shape(value, assignments) for value in (node.left, node.right)})
    return _call_shape(node, assignments) if isinstance(node, ast.Call) else ""


def _call_shape(node: ast.Call, assignments: dict[str, str]) -> str:
    if is_receiver_request_dispatch(node):
        return "DispatchedResult"
    raw_name = _call_name(node.func); name = raw_name.lower()
    if name == "isinstance": return "bool"
    if any(token in name for token in ("render", "request", "response", "redirect")): return "ResponseLike"
    if name.endswith(("dict", "to_dict", "kwargs")): return "MappingLike"
    owner, _, operation = name.rpartition(".")
    if operation == "get" and any(token in owner.split(".") for token in ("crud", "repo", "repository")): return "EntityLike"
    if name.endswith(("list", "all")): return "SequenceLike"
    if name.startswith("self.") and any(expression_shape(arg, assignments) == "ArrayLike" for arg in node.args): return "ArrayLike"
    if name.endswith(("numpy", "array", "astype", "tile", "reshape", "transpose", "stack", "concatenate", "hstack", "vstack", "split")): return "ArrayLike"
    if name.startswith(ARRAY_PREFIXES) and name.endswith(ARRAY_CALL_SUFFIXES): return "ArrayLike"
    if name.endswith(("_item", "from_json")): return "ItemLike"
    if name.endswith(("format", "replace", "strip", "translate", "zfill")): return "str"
    if name.endswith(("unpad", "unpadding")): return "bytes"
    if name.endswith(("image.frombytes", "image.fromarray")): return "ImageLike"
    xml_shape = xml_call_shape(name)
    if xml_shape: return xml_shape
    if raw_name.rsplit(".", 1)[-1][:1].isupper(): return f"ConstructedObject[{raw_name.rsplit('.', 1)[-1]}]"
    if name.endswith((".execute", ".executemany")): return "DatabaseResult"
    return ""


def _call_name(node: ast.AST | None) -> str:
    if isinstance(node, ast.Name): return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""
