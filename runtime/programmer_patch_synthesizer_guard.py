"""Required-input guard synthesis helpers."""

from __future__ import annotations

import ast
from typing import Any

from .python_parser_compatibility import parse_compatible_source
from .programmer_patch_synthesizer_helper_extractors import _find_top_level_function

def _required_input_keys(test_plan: dict[str, Any], target: str, recipe: dict[str, Any]) -> list[str]:
    executable = dict(test_plan.get("executable_acceptance", {}))
    obligations = [dict(item) for item in executable.get("obligations", []) if isinstance(item, dict)]
    keys: list[str] = []
    missing = dict(recipe.get("missing_input_case") or {})
    missing_kind = missing.get("kind", "malformed_input_case")
    missing_given = missing.get("given", {})
    has_missing_case = any(
        row.get("target") == target and row.get("kind") == missing_kind and row.get("given") == missing_given
        for row in obligations
    )
    if not has_missing_case:
        return []
    positive_kind = str(recipe.get("positive_case_kind") or "positive_contract_case")
    for row in obligations:
        if row.get("target") != target or row.get("kind") != positive_kind:
            continue
        given = row.get("given", {})
        if not isinstance(given, dict):
            continue
        for key in given:
            text = str(key)
            if text.isidentifier() and text not in keys:
                keys.append(text)
    return keys[: int(recipe.get("max_required_inputs") or 8)]

def _guard_evidence(contract_keys: list[str], signature_keys: list[str], guard_keys: list[str]) -> dict[str, Any]:
    source = "contract_missing_input_case" if contract_keys else "signature_required_parameters"
    return {"source": source, "contract_keys": contract_keys, "signature_keys": signature_keys, "guarded_keys": guard_keys}

def _required_signature_keys(source: str, function_name: str, recipe: dict[str, Any]) -> list[str]:
    try:
        tree, _ = parse_compatible_source(source, "<patch-source>")
    except SyntaxError:
        return []
    function = _find_patchable_function(tree, function_name)
    if function is None:
        return []
    keys: list[str] = []
    ignored = {str(item) for item in recipe.get("ignored_signature_parameters", [])}
    defaults = len(function.args.defaults)
    positional = function.args.posonlyargs + function.args.args
    required_positional = positional[: len(positional) - defaults] if defaults else positional
    for arg in required_positional:
        if arg.arg not in ignored:
            keys.append(arg.arg)
    for arg, default in zip(function.args.kwonlyargs, function.args.kw_defaults):
        if default is None:
            keys.append(arg.arg)
    return [key for key in keys if key.isidentifier()][: int(recipe.get("max_required_inputs") or 8)]

def _guard_required_keys(source: str, function_name: str, required_keys: list[str]) -> list[str]:
    try:
        tree, _ = parse_compatible_source(source, "<patch-source>")
    except SyntaxError:
        return []
    function = _find_patchable_function(tree, function_name)
    if function is None:
        return []
    defaulted = _defaulted_parameters(function)
    named_args = {arg.arg for arg in function.args.posonlyargs + function.args.args + function.args.kwonlyargs}
    return [key for key in required_keys if key not in defaulted and (key in named_args or function.args.kwarg)]

def _defaulted_parameters(function: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    positional = function.args.posonlyargs + function.args.args
    defaults = function.args.defaults
    defaulted = {arg.arg for arg in positional[len(positional) - len(defaults) :]}
    defaulted.update(arg.arg for arg, default in zip(function.args.kwonlyargs, function.args.kw_defaults) if default is not None)
    return defaulted

def _patch_required_input_guard(source: str, function_name: str, required_keys: list[str], recipe: dict[str, Any]) -> str:
    try:
        tree, _ = parse_compatible_source(source, "<patch-source>")
    except SyntaxError:
        return source
    function = _find_patchable_function(tree, function_name)
    if function is None:
        return source
    lines = source.splitlines()
    if _function_already_has_guard(lines, function, required_keys, recipe):
        return source
    indent = _body_indent(lines, function)
    insert_at = _guard_insert_line(function)
    guard = _guard_lines(function, required_keys, indent, recipe)
    if not guard:
        return source
    patched = lines[:insert_at] + guard + lines[insert_at:]
    return "\n".join(patched) + ("\n" if source.endswith("\n") else "")

def _find_patchable_function(tree: ast.Module, function_name: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    top_level = _find_top_level_function(tree, function_name)
    if top_level is not None:
        return top_level
    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name
    ]
    return matches[0] if len(matches) == 1 else None

def _function_already_has_guard(
    lines: list[str],
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    required_keys: list[str],
    recipe: dict[str, Any],
) -> bool:
    body = "\n".join(lines[function.lineno - 1 : function.end_lineno or function.lineno])
    markers = [str(item) for item in recipe.get("already_present_markers", [])]
    return all(any(marker.format(key=key) in body for marker in markers) for key in required_keys)

def _body_indent(lines: list[str], function: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    if function.body:
        line = lines[function.body[0].lineno - 1]
        return line[: len(line) - len(line.lstrip())]
    line = lines[function.lineno - 1]
    return line[: len(line) - len(line.lstrip())] + "    "

def _guard_insert_line(function: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    if function.body and isinstance(function.body[0], ast.Expr) and isinstance(function.body[0].value, ast.Constant):
        return function.body[0].end_lineno or function.body[0].lineno
    if function.body:
        return function.body[0].lineno - 1
    return function.lineno

def _guard_lines(function: ast.FunctionDef | ast.AsyncFunctionDef, required_keys: list[str], indent: str, recipe: dict[str, Any]) -> list[str]:
    named_args = {arg.arg for arg in function.args.posonlyargs + function.args.args + function.args.kwonlyargs}
    kwargs_name = function.args.kwarg.arg if function.args.kwarg else None
    lines: list[str] = []
    named_template = [str(item) for item in recipe.get("named_argument_guard", [])]
    kwargs_template = [str(item) for item in recipe.get("kwargs_guard", [])]
    for key in required_keys:
        if kwargs_name and key not in named_args:
            lines.extend(f"{indent}{line.format(key=key, kwargs=kwargs_name)}" for line in kwargs_template)
        elif key in named_args:
            lines.extend(f"{indent}{line.format(key=key, kwargs=kwargs_name or '')}" for line in named_template)
    return lines
