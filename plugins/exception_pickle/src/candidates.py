"""Static detector for custom exceptions whose default pickle replay cannot call __init__."""

from __future__ import annotations

import ast
from typing import Any


def _candidate(
    owner: ast.ClassDef, *, local_classes: dict[str, ast.ClassDef] | None = None
) -> dict[str, Any] | None:
    if not _exception_shaped(owner):
        return None
    methods = {
        node.name: node for node in owner.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    constructor = methods.get("__init__")
    if not isinstance(constructor, ast.FunctionDef) or _has_reconstruction_hook(
        owner, local_classes or {owner.name: owner}
    ):
        return None
    positional = [*constructor.args.posonlyargs, *constructor.args.args]
    names = [node.arg for node in positional]
    if not names or names[0] not in {"self", "cls"}:
        return None
    positional_parameters = names[1:]
    kwonly_parameters = [node.arg for node in constructor.args.kwonlyargs]
    parameters = [*positional_parameters, *kwonly_parameters]
    default_count = len(constructor.args.defaults)
    required_positional_count = max(0, len(positional_parameters) - default_count)
    required = positional_parameters[:required_positional_count]
    required.extend(
        argument.arg
        for argument, default in zip(constructor.args.kwonlyargs, constructor.args.kw_defaults)
        if default is None
    )
    if not required:
        return None
    super_calls = [
        node for node in ast.walk(constructor)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "__init__"
        and isinstance(node.func.value, ast.Call)
        and isinstance(node.func.value.func, ast.Name)
        and node.func.value.func.id == "super"
    ]
    if len(super_calls) != 1:
        return None
    replay_names = [node.id for node in super_calls[0].args if isinstance(node, ast.Name)]
    if len(replay_names) == len(super_calls[0].args) and replay_names[: len(required)] == required:
        return None
    stored = sorted({
        node.value.id
        for node in ast.walk(constructor)
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
        if isinstance(target, ast.Attribute)
        and isinstance(target.value, ast.Name)
        and target.value.id == "self"
        and isinstance(node.value, ast.Name)
        and node.value.id in parameters
    })
    formatted = any(
        isinstance(argument, (ast.JoinedStr, ast.BinOp, ast.Call))
        or isinstance(argument, ast.Name) and argument.id not in parameters
        for argument in super_calls[0].args
    )
    return {
        "class_name": owner.name,
        "line": owner.lineno,
        "constructor_parameters": parameters,
        "required_constructor_parameters": required,
        "stored_constructor_parameters": stored,
        "base_exception_arguments": [ast.unparse(node) for node in super_calls[0].args],
        "formatted_super_argument": formatted,
        "default_pickle_replay_incompatible": True,
    }


def _has_reconstruction_hook(
    owner: ast.ClassDef,
    local_classes: dict[str, ast.ClassDef],
    seen: set[str] | None = None,
) -> bool:
    hooks = {"__reduce__", "__reduce_ex__", "__getnewargs__", "__getnewargs_ex__"}
    if any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in hooks
        for node in owner.body
    ):
        return True
    visited = set(seen or ())
    if owner.name in visited:
        return False
    visited.add(owner.name)
    for base in owner.bases:
        base_name = base.id if isinstance(base, ast.Name) else None
        parent = local_classes.get(base_name or "")
        if parent is not None and _has_reconstruction_hook(parent, local_classes, visited):
            return True
    return False


def _exception_shaped(owner: ast.ClassDef) -> bool:
    if owner.name.endswith(("Error", "Exception")):
        return True
    return any(
        (
            isinstance(base, ast.Name) and base.id.endswith(("Error", "Exception"))
        ) or (
            isinstance(base, ast.Attribute) and base.attr.endswith(("Error", "Exception"))
        )
        for base in owner.bases
    )
