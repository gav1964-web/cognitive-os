"""Propagate structural samples through direct same-module helper calls."""

from __future__ import annotations

import ast
from typing import Any

from .executable_acceptance_structural_samples import collect_structural_samples

Candidates = dict[str, list[tuple[int, Any, str]]]
FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


def add_local_call_samples(
    tree: ast.Module,
    node: FunctionNode,
    parameters: set[str],
    candidates: Candidates,
) -> None:
    functions = {
        item.name: item
        for item in tree.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item is not node
    }
    for call in ast.walk(node):
        if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name):
            continue
        callee = functions.get(call.func.id)
        if callee is None:
            continue
        callee_names = _parameter_names(callee)
        propagated = {name: [] for name in callee_names}
        collect_structural_samples(tree, callee, callee_names, propagated)
        bindings = _bindings(call, callee)
        for callee_name, caller_name in bindings.items():
            if caller_name not in parameters:
                continue
            candidates[caller_name].extend(
                (priority, value, f"local_call:{call.func.id}:{source}")
                for priority, value, source in propagated.get(callee_name, [])
                if isinstance(value, dict) and value.get("__fixture__") == "declared_model"
            )


def _parameter_names(node: FunctionNode) -> set[str]:
    args = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
    return {item.arg for item in args if item.arg not in {"self", "cls"}}


def _bindings(call: ast.Call, callee: FunctionNode) -> dict[str, str]:
    positional = [*callee.args.posonlyargs, *callee.args.args]
    result = {
        parameter.arg: argument.id
        for parameter, argument in zip(positional, call.args)
        if isinstance(argument, ast.Name)
    }
    result.update({
        keyword.arg: keyword.value.id
        for keyword in call.keywords
        if keyword.arg and isinstance(keyword.value, ast.Name)
    })
    return result
