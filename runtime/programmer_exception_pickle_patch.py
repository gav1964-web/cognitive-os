"""Strict source edit for custom exceptions that cannot replay constructor inputs."""

from __future__ import annotations

import ast
from typing import Any


def exception_pickle_reconstruction_patch(
    source: str, *, class_name: str, recipe: dict[str, Any], constructor_name: str = "__init__"
) -> dict[str, Any] | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    owner = next(
        (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name),
        None,
    )
    if owner is None or not owner.bases:
        return None
    constructor = next(
        (
            node for node in owner.body
            if isinstance(node, ast.FunctionDef) and node.name == constructor_name
        ),
        None,
    )
    required_inputs = [str(value) for value in recipe.get("required_constructor_inputs") or []]
    reconstruction_method = str(recipe.get("reconstruction_method") or "")
    state_strategy = str(recipe.get("state_strategy") or "")
    if not state_strategy and required_inputs == ["allowed", "host"]:
        state_strategy = "insert_private_exact"
    if (
        not required_inputs
        or len(required_inputs) > 4
        or reconstruction_method != "__reduce__"
        or state_strategy not in {
        "insert_private_exact",
        "reuse_direct_assignments",
        }
    ):
        return None
    if constructor is None or any(
        isinstance(node, ast.FunctionDef) and node.name == reconstruction_method
        for node in owner.body
    ):
        return None
    positional = [*constructor.args.posonlyargs, *constructor.args.args]
    keyword_only = [node.arg for node in constructor.args.kwonlyargs]
    positional_names = [node.arg for node in positional]
    constructor_inputs = positional_names[1:] + keyword_only
    if not set(required_inputs) <= set(constructor_inputs):
        return None
    if not constructor.body:
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
    state_attributes = _direct_state_attributes(constructor, required_inputs)
    if state_strategy == "insert_private_exact":
        if required_inputs != ["allowed", "host"] or state_attributes:
            return None
        state_attributes = {"allowed": "_allowed", "host": "_host"}
    elif set(state_attributes) != set(required_inputs):
        return None

    first_line = int(constructor.body[0].lineno) - 1
    end_line = int(getattr(constructor, "end_lineno", constructor.lineno))
    lines = source.splitlines(keepends=True)
    newline = "\r\n" if "\r\n" in source else "\n"
    body_indent = _line_indent(lines[first_line])
    method_indent = _line_indent(lines[int(constructor.lineno) - 1])
    state_lines = []
    if state_strategy == "insert_private_exact":
        state_lines = [
            f"{body_indent}self._allowed = allowed{newline}",
            f"{body_indent}self._host = host{newline}",
        ]
    uses_keyword_only = any(name in keyword_only for name in required_inputs)
    if uses_keyword_only:
        if recipe.get("allow_keyword_only_state_reducer") is not True:
            return None
        reduce_lines = [
            newline,
            f"{method_indent}def {reconstruction_method}(self):{newline}",
            f"{method_indent}    return (BaseException.__new__, (self.__class__, *self.args), self.__dict__){newline}",
        ]
    else:
        if positional_names[: len(required_inputs) + 1] != ["self", *required_inputs]:
            return None
        replay = ", ".join(f"self.{state_attributes[name]}" for name in required_inputs)
        if len(required_inputs) == 1:
            replay += ","
        reduce_lines = [
            newline,
            f"{method_indent}def {reconstruction_method}(self):{newline}",
            f"{method_indent}    return (self.__class__, ({replay})){newline}",
        ]
    patched = "".join(lines[:first_line] + state_lines + lines[first_line:end_line] + reduce_lines + lines[end_line:])
    try:
        patched_tree = ast.parse(patched)
    except SyntaxError:
        return None
    patched_owner = next(
        (node for node in patched_tree.body if isinstance(node, ast.ClassDef) and node.name == class_name),
        None,
    )
    if patched_owner is None or not any(
        isinstance(node, ast.FunctionDef) and node.name == reconstruction_method
        for node in patched_owner.body
    ):
        return None
    return {
        "source": patched,
        "class_name": class_name,
        "constructor_name": constructor_name,
        "stored_inputs": required_inputs,
        "state_strategy": state_strategy,
        "reconstruction_method": reconstruction_method,
    }


def _direct_state_attributes(
    constructor: ast.FunctionDef, required_inputs: list[str]
) -> dict[str, str]:
    attributes: dict[str, str] = {}
    for node in ast.walk(constructor):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)) or not isinstance(node.value, ast.Name):
            continue
        if node.value.id not in required_inputs:
            continue
        targets = list(node.targets) if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
            ):
                if node.value.id in attributes and attributes[node.value.id] != target.attr:
                    return {}
                attributes[node.value.id] = target.attr
    return attributes


def _line_indent(line: str) -> str:
    return line[: len(line) - len(line.lstrip(" \t"))]
