"""Deterministic sandbox patch synthesis for small Python function targets."""

from __future__ import annotations

import ast
import difflib
import os
import shutil
from pathlib import Path
from typing import Any

from .patch_synthesis_policy import required_input_guard_recipe

NO_PATCH = {"status": "skipped", "reason": "no_supported_patch_pattern", "patches": []}


def synthesize_patch_package(
    *,
    execution_dir: Path,
    project_dir: Path,
    implementation_plan: dict[str, Any],
    test_plan: dict[str, Any],
) -> dict[str, Any]:
    target = _target_symbol(implementation_plan)
    if not target:
        return dict(NO_PATCH)
    path_text, _, symbol = target.partition(":")
    if not path_text.endswith(".py") or not symbol or "." in symbol:
        return dict(NO_PATCH)
    if path_text not in _expected_files(implementation_plan):
        return {"status": "blocked", "reason": "target_file_not_in_expected_files", "patches": []}
    recipe = required_input_guard_recipe()
    if not recipe:
        return dict(NO_PATCH)

    sandbox_project = execution_dir / "patch_sandbox" / "project"
    _copy_project(project_dir, sandbox_project)
    source = (sandbox_project / path_text).resolve()
    try:
        source.relative_to(sandbox_project.resolve())
    except ValueError:
        return {"status": "blocked", "reason": "target_outside_sandbox", "patches": []}
    if not source.is_file():
        return {"status": "blocked", "reason": "target_file_missing_in_sandbox", "patches": []}

    original = source.read_text(encoding="utf-8")
    signature_keys = _required_signature_keys(original, symbol, recipe)
    required_keys = _required_input_keys(test_plan, target, recipe) or signature_keys
    if not required_keys:
        return dict(NO_PATCH)
    guard_keys = _guard_required_keys(original, symbol, required_keys)
    if not guard_keys and signature_keys and required_keys != signature_keys:
        guard_keys = _guard_required_keys(original, symbol, signature_keys)
    if not guard_keys:
        return dict(NO_PATCH)
    patched = _patch_required_input_guard(original, symbol, guard_keys, recipe)
    if patched == original:
        return dict(NO_PATCH)
    source.write_text(patched, encoding="utf-8")
    diff = list(
        difflib.unified_diff(
            original.splitlines(),
            patched.splitlines(),
            fromfile=f"a/{path_text}",
            tofile=f"b/{path_text}",
            lineterm="",
        )
    )
    return {
        "status": str(recipe.get("status") or "prepared"),
        "reason": str(recipe.get("reason") or "required_input_guard_synthesized"),
        "sandbox_project": sandbox_project.as_posix(),
        "patches": [
            {
                "artifact_type": "PatchOperation",
                "kind": str(recipe.get("operation_kind") or "insert_required_input_guard"),
                "target": target,
                "file": path_text,
                "required_inputs": guard_keys,
                "diff": diff,
            }
        ],
    }


def _target_symbol(implementation_plan: dict[str, Any]) -> str:
    intent = dict(implementation_plan.get("patch_intent", {}))
    target = str(intent.get("target_symbol") or "")
    if target:
        return target
    return str(dict(implementation_plan.get("implementation_target", {})).get("candidate") or "")


def _expected_files(implementation_plan: dict[str, Any]) -> list[str]:
    return [str(item).split(":", 1)[0] for item in implementation_plan.get("expected_files", []) if item]


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


def _required_signature_keys(source: str, function_name: str, recipe: dict[str, Any]) -> list[str]:
    try:
        tree = ast.parse(source)
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


def _copy_project(project_dir: Path, sandbox_project: Path) -> None:
    if sandbox_project.exists():
        _remove_tree(sandbox_project)
    shutil.copytree(
        project_dir,
        sandbox_project,
        ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", "artifacts", "reports"),
    )


def _remove_tree(path: Path) -> None:
    def onerror(function: object, name: str, exc_info: object) -> None:
        try:
            os.chmod(name, 0o700)
            function(name)
        except OSError:
            pass

    shutil.rmtree(path, onerror=onerror)


def _guard_required_keys(source: str, function_name: str, required_keys: list[str]) -> list[str]:
    tree = ast.parse(source)
    function = _find_patchable_function(tree, function_name)
    if function is None:
        return []
    defaulted = _defaulted_parameters(function)
    named_args = {arg.arg for arg in function.args.args + function.args.kwonlyargs}
    return [key for key in required_keys if key not in defaulted and (key in named_args or function.args.kwarg)]


def _defaulted_parameters(function: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    positional = function.args.args
    defaults = function.args.defaults
    defaulted = {arg.arg for arg in positional[len(positional) - len(defaults) :]}
    defaulted.update(arg.arg for arg, default in zip(function.args.kwonlyargs, function.args.kw_defaults) if default is not None)
    return defaulted


def _patch_required_input_guard(source: str, function_name: str, required_keys: list[str], recipe: dict[str, Any]) -> str:
    tree = ast.parse(source)
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


def _find_top_level_function(tree: ast.Module, function_name: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    return next(
        (
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name
        ),
        None,
    )


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
    named_args = {arg.arg for arg in function.args.args + function.args.kwonlyargs}
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
