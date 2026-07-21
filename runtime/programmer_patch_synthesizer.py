"""Deterministic sandbox patch synthesis for small Python function targets."""

from __future__ import annotations

import ast
import difflib
import shutil
from pathlib import Path
from typing import Any


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

    required_keys = _required_input_keys(test_plan, target)
    if not required_keys:
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
    patched = _patch_required_input_guard(original, symbol, required_keys)
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
        "status": "prepared",
        "reason": "required_input_guard_synthesized",
        "sandbox_project": sandbox_project.as_posix(),
        "patches": [
            {
                "artifact_type": "PatchOperation",
                "kind": "insert_required_input_guard",
                "target": target,
                "file": path_text,
                "required_inputs": required_keys,
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


def _required_input_keys(test_plan: dict[str, Any], target: str) -> list[str]:
    executable = dict(test_plan.get("executable_acceptance", {}))
    obligations = [dict(item) for item in executable.get("obligations", []) if isinstance(item, dict)]
    keys: list[str] = []
    has_missing_case = any(
        row.get("target") == target and row.get("kind") == "malformed_input_case" and row.get("given") == {}
        for row in obligations
    )
    if not has_missing_case:
        return []
    for row in obligations:
        if row.get("target") != target or row.get("kind") != "positive_contract_case":
            continue
        given = row.get("given", {})
        if not isinstance(given, dict):
            continue
        for key in given:
            text = str(key)
            if text.isidentifier() and text not in keys:
                keys.append(text)
    return keys[:8]


def _copy_project(project_dir: Path, sandbox_project: Path) -> None:
    if sandbox_project.exists():
        shutil.rmtree(sandbox_project)
    shutil.copytree(
        project_dir,
        sandbox_project,
        ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", "artifacts", "reports"),
    )


def _patch_required_input_guard(source: str, function_name: str, required_keys: list[str]) -> str:
    tree = ast.parse(source)
    function = next((node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == function_name), None)
    if function is None:
        return source
    lines = source.splitlines()
    if _function_already_has_guard(lines, function, required_keys):
        return source
    indent = _body_indent(lines, function)
    insert_at = _guard_insert_line(function)
    guard = _guard_lines(function, required_keys, indent)
    if not guard:
        return source
    patched = lines[:insert_at] + guard + lines[insert_at:]
    return "\n".join(patched) + ("\n" if source.endswith("\n") else "")


def _function_already_has_guard(lines: list[str], function: ast.FunctionDef, required_keys: list[str]) -> bool:
    body = "\n".join(lines[function.lineno - 1 : function.end_lineno or function.lineno])
    return all(f"{key} required" in body or f"{key!r} not in kwargs" in body or f'"{key}" not in kwargs' in body for key in required_keys)


def _body_indent(lines: list[str], function: ast.FunctionDef) -> str:
    if function.body:
        line = lines[function.body[0].lineno - 1]
        return line[: len(line) - len(line.lstrip())]
    line = lines[function.lineno - 1]
    return line[: len(line) - len(line.lstrip())] + "    "


def _guard_insert_line(function: ast.FunctionDef) -> int:
    if function.body and isinstance(function.body[0], ast.Expr) and isinstance(function.body[0].value, ast.Constant):
        return function.body[0].end_lineno or function.body[0].lineno
    return function.lineno


def _guard_lines(function: ast.FunctionDef, required_keys: list[str], indent: str) -> list[str]:
    named_args = {arg.arg for arg in function.args.args + function.args.kwonlyargs}
    kwargs_name = function.args.kwarg.arg if function.args.kwarg else None
    lines: list[str] = []
    for key in required_keys:
        if kwargs_name and key not in named_args:
            lines.extend(
                [
                    f'{indent}if "{key}" not in {kwargs_name}:',
                    f'{indent}    raise ValueError("{key} required")',
                ]
            )
        elif key in named_args:
            lines.extend(
                [
                    f"{indent}if {key} is None:",
                    f'{indent}    raise ValueError("{key} required")',
                ]
            )
    return lines
