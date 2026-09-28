"""Contract-derived identity-return transform patch recipe for Programmer Executor."""

from __future__ import annotations

import ast
from typing import Any

from .contract_transform_operators import operator_records


def contract_transform_patch(
    source: str,
    function_name: str,
    target: str,
    path_text: str,
    test_plan: dict[str, Any],
    recipe: dict[str, Any],
) -> dict[str, Any] | None:
    contract = _single_arg_contract(test_plan, target, recipe)
    if contract is None:
        return None
    transform = _matching_transform(
        contract["input"], contract["expected"], recipe, declared_operator=contract.get("operator_id")
    )
    if transform is None:
        return None
    tree = ast.parse(source)
    function = _find_patchable_function(tree, function_name)
    body_kind = _patchable_body_kind(function, contract["arg"]) if function else ""
    if function is None or not body_kind or not _arg_in_signature(function, contract["arg"]):
        return None
    lines = source.splitlines()
    indent = _body_indent(lines, function)
    start = function.body[0].lineno - 1
    end = function.body[-1].end_lineno or function.body[-1].lineno
    patched = lines[:start] + [f"{indent}return {_return_expression(contract['arg'], transform['id'])}"] + lines[end:]
    return {
        "source": "\n".join(patched) + ("\n" if source.endswith("\n") else ""),
        "transform": transform["id"],
        "transform_evidence": {
            "source": "contract_identity_transform_case",
            "target": target,
            "file": path_text,
            "argument": contract["arg"],
            "input_sample": contract["input"],
            "expected": contract["expected"],
            "body_kind": body_kind,
        },
    }


def _single_arg_contract(test_plan: dict[str, Any], target: str, recipe: dict[str, Any]) -> dict[str, Any] | None:
    positive_kind = str(recipe.get("positive_case_kind") or "positive_contract_case")
    expect_keys = [str(item) for item in list(recipe.get("expect_keys") or [])]
    for row in list(dict(test_plan.get("executable_acceptance") or {}).get("obligations") or []):
        if not isinstance(row, dict) or row.get("target") != target or row.get("kind") != positive_kind:
            continue
        given = row.get("given")
        expect = row.get("expect")
        if not isinstance(given, dict) or len(given) != 1 or not isinstance(expect, dict):
            continue
        arg, value = next(iter(given.items()))
        if not str(arg).isidentifier() or not _sample_is_safe(value):
            continue
        for key in expect_keys:
            expected = expect.get(key)
            if _sample_is_safe(expected):
                profile = dict(row.get("contract_profile") or {})
                return {
                    "arg": str(arg),
                    "input": value,
                    "expected": expected,
                    "operator_id": str(profile.get("operator_id") or ""),
                }
    return None


def _matching_transform(
    value: Any,
    expected: Any,
    recipe: dict[str, Any],
    *,
    declared_operator: object = None,
) -> dict[str, str] | None:
    records = operator_records(recipe)
    declared = str(declared_operator or "")
    for record in records:
        if declared and record.get("id") == declared and value != expected:
            return {"id": declared, "expression_template": str(record.get("expression_template") or "")}
    for record in records:
        transform_id = str(record.get("id") or "")
        if _apply_transform(transform_id, value) == expected and value != expected:
            return {"id": transform_id, "expression_template": str(record.get("expression_template") or "")}
    return None


def _apply_transform(transform_id: str, value: Any) -> Any:
    if transform_id == "strip" and isinstance(value, str):
        return value.strip()
    if transform_id == "lower" and isinstance(value, str):
        return value.lower()
    if transform_id == "upper" and isinstance(value, str):
        return value.upper()
    if transform_id == "strip_lower" and isinstance(value, str):
        return value.strip().lower()
    if transform_id == "strip_upper" and isinstance(value, str):
        return value.strip().upper()
    if transform_id == "comma_split_strip_nonempty" and isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if transform_id == "sum_numbers" and _number_list(value):
        return sum(value)
    if transform_id == "len_sequence" and isinstance(value, (str, list, dict)):
        return len(value)
    if transform_id == "first_item" and isinstance(value, (str, list)) and value:
        return value[0]
    if transform_id == "last_item" and isinstance(value, (str, list)) and value:
        return value[-1]
    if transform_id == "sorted_list" and isinstance(value, list):
        return sorted(value)
    if transform_id == "unique_preserve_order" and isinstance(value, list):
        return list(dict.fromkeys(value))
    return object()


def _return_expression(arg: str, transform_id: str) -> str:
    for record in operator_records({"allowed_transforms": [transform_id]}):
        return str(record.get("expression_template") or "{arg}").replace("{arg}", arg)
    raise KeyError(transform_id)


def _patchable_body_kind(function: ast.FunctionDef | ast.AsyncFunctionDef, arg: str) -> str:
    body = [node for node in function.body if not _doc_expr(node)]
    if len(body) != 1:
        return ""
    node = body[0]
    if isinstance(node, ast.Return) and isinstance(node.value, ast.Name) and node.value.id == arg:
        return "identity_return"
    if isinstance(node, ast.Pass):
        return "pass_stub"
    if isinstance(node, ast.Return) and (node.value is None or (isinstance(node.value, ast.Constant) and node.value.value is None)):
        return "none_stub"
    if isinstance(node, ast.Raise) and _raises_notimplemented(node):
        return "notimplemented_stub"
    return ""


def _arg_in_signature(function: ast.FunctionDef | ast.AsyncFunctionDef, arg: str) -> bool:
    return arg in {item.arg for item in function.args.posonlyargs + function.args.args + function.args.kwonlyargs}


def _raises_notimplemented(node: ast.Raise) -> bool:
    exc = node.exc
    if isinstance(exc, ast.Name):
        return exc.id == "NotImplementedError"
    return isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name) and exc.func.id == "NotImplementedError"


def _find_patchable_function(tree: ast.Module, function_name: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name
    ]
    return matches[0] if len(matches) == 1 else None


def _sample_is_safe(value: Any) -> bool:
    if value is None or isinstance(value, (str, int, float, bool)):
        return True
    if isinstance(value, list):
        return all(_sample_is_safe(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and _sample_is_safe(item) for key, item in value.items())
    return False


def _number_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in value)


def _doc_expr(node: ast.AST) -> bool:
    return isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)


def _body_indent(lines: list[str], function: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    line = lines[function.body[0].lineno - 1]
    return line[: len(line) - len(line.lstrip())]
