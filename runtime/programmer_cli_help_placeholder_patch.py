"""Bounded type-placeholder map edit for a proven Invoke CLI help defect."""

from __future__ import annotations

import ast
from typing import Any


def cli_help_placeholder_patch(
    source: str, *, symbol: str, recipe: dict[str, Any]
) -> dict[str, Any] | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    required_symbol = str(recipe.get("required_symbol") or "")
    if symbol != required_symbol:
        return None
    function = _qualified_function(tree, required_symbol)
    if function is None or _shadows_builtins(tree, function, {"str", "int"}):
        return None
    mappings = [
        node.func.value
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
        and isinstance(node.func.value, ast.Dict)
        and _is_kind_lookup(node)
    ]
    if len(mappings) != 1 or not _is_exact_string_mapping(mappings[0], recipe):
        return None
    mapping = mappings[0]
    key = mapping.keys[0]
    value = mapping.values[0]
    if not isinstance(key, ast.Name) or not isinstance(value, ast.Constant):
        return None
    lines = source.splitlines(keepends=True)
    line_index = int(key.lineno) - 1
    line = lines[line_index]
    newline = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
    content = line[: -len(newline)] if newline else line
    value_source = ast.get_source_segment(source, value)
    existing_type = str(recipe.get("existing_type_name") or "")
    added_type = str(recipe.get("added_type_name") or "")
    if not added_type or content.strip() != f"{existing_type}: {value_source},":
        return None
    indent = content[: len(content) - len(content.lstrip())]
    placeholder = str(recipe.get("added_placeholder") or "")
    quote = '"' if str(value_source).startswith('"') else "'"
    lines.insert(
        line_index + 1,
        f"{indent}{added_type}: {quote}{placeholder}{quote},{newline}",
    )
    patched = "".join(lines)
    try:
        ast.parse(patched)
    except SyntaxError:
        return None
    return {
        "source": patched,
        "existing_type": existing_type,
        "added_type": added_type,
        "added_placeholder": placeholder,
    }


def _qualified_function(
    tree: ast.Module, required_symbol: str
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    owner_name, separator, function_name = required_symbol.partition(".")
    if not separator:
        return None
    owners = [
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == owner_name
    ]
    if len(owners) != 1:
        return None
    functions = [
        node for node in owners[0].body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == function_name
    ]
    return functions[0] if len(functions) == 1 else None


def _is_kind_lookup(node: ast.Call) -> bool:
    return (
        len(node.args) == 1
        and not node.keywords
        and isinstance(node.args[0], ast.Attribute)
        and isinstance(node.args[0].value, ast.Name)
        and node.args[0].value.id == "arg"
        and node.args[0].attr == "kind"
    )


def _is_exact_string_mapping(mapping: ast.Dict, recipe: dict[str, Any]) -> bool:
    return (
        len(mapping.keys) == 1
        and len(mapping.values) == 1
        and isinstance(mapping.keys[0], ast.Name)
        and mapping.keys[0].id == str(recipe.get("existing_type_name") or "")
        and isinstance(mapping.values[0], ast.Constant)
        and mapping.values[0].value == recipe.get("existing_placeholder")
        and bool(recipe.get("added_placeholder"))
    )


def _shadows_builtins(
    tree: ast.Module,
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    names: set[str],
) -> bool:
    module_bindings = _module_bindings(tree)
    local_bindings = {
        node.id
        for node in ast.walk(function)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
    }
    local_bindings.update(
        node.name
        for node in ast.walk(function)
        if node is not function
        and isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    )
    arguments = [
        *function.args.posonlyargs,
        *function.args.args,
        *function.args.kwonlyargs,
    ]
    argument_names = {argument.arg for argument in arguments}
    if function.args.vararg:
        argument_names.add(function.args.vararg.arg)
    if function.args.kwarg:
        argument_names.add(function.args.kwarg.arg)
    return bool(names.intersection(module_bindings | local_bindings | argument_names))


def _module_bindings(tree: ast.Module) -> set[str]:
    result: set[str] = set()
    for statement in tree.body:
        if isinstance(statement, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            result.add(statement.name)
        elif isinstance(statement, ast.Import):
            result.update(alias.asname or alias.name.split(".", 1)[0] for alias in statement.names)
        elif isinstance(statement, ast.ImportFrom):
            result.update(alias.asname or alias.name for alias in statement.names)
        else:
            result.update(
                node.id
                for node in ast.walk(statement)
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
            )
    return result
