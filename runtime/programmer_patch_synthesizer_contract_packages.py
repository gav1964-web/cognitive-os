"""Failure-kind specific deterministic patch package builders."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .patch_synthesis_policy import (
    duplicate_cli_short_option_contract_recipe,
    escaped_fstring_brace_offset_contract_recipe,
    falsy_primitive_empty_contract_recipe,
    framework_contract_recipe,
    incomplete_import_token_contract_recipe,
    missing_registry_env_fallback_recipe,
    strict_default_string_comparison_contract_recipe,
    timestamp_range_error_contract_recipe,
    trailing_backslash_bounds_contract_recipe,
)
from .programmer_duplicate_cli_option_patch import duplicate_cli_option_patch
from .programmer_falsy_empty_patch import falsy_primitive_empty_patch
from .programmer_framework_contract_patch import framework_contract_patch
from .programmer_fstring_brace_offset_patch import fstring_brace_offset_patch
from .programmer_incomplete_import_patch import incomplete_import_token_patch
from .programmer_patch_synthesizer_common import NO_PATCH, _copy_project, _patch_result
from .programmer_registry_fallback_patch import registry_env_fallback_patch
from .programmer_strict_default_comparison_patch import strict_default_comparison_patch
from .programmer_timestamp_range_patch import timestamp_range_error_patch
from .programmer_trailing_backslash_patch import trailing_backslash_bounds_patch

def _registry_fallback_package(
    *,
    execution_dir: Path,
    project_dir: Path,
    target: str,
    path_text: str,
    symbol: str,
) -> dict[str, Any]:
    recipe = missing_registry_env_fallback_recipe()
    if not recipe:
        return {**NO_PATCH, "reason": "missing_registry_fallback_recipe_disabled"}
    sandbox_project = execution_dir / "patch_sandbox" / "project"
    _copy_project(project_dir, sandbox_project)
    source_path = (sandbox_project / path_text).resolve()
    try:
        source_path.relative_to(sandbox_project.resolve())
    except ValueError:
        return {"status": "blocked", "reason": "target_outside_sandbox", "patches": []}
    if not source_path.is_file():
        return {"status": "blocked", "reason": "target_file_missing_in_sandbox", "patches": []}
    original = source_path.read_text(encoding="utf-8")
    patch = registry_env_fallback_patch(original, symbol=symbol, recipe=recipe)
    if patch is None:
        return {**NO_PATCH, "reason": "missing_registry_fallback_pattern_not_proven"}
    patched = str(patch["source"])
    source_path.write_text(patched, encoding="utf-8")
    return _patch_result(
        recipe=recipe,
        sandbox_project=sandbox_project,
        path_text=path_text,
        target=target,
        original=original,
        patched=patched,
        operation={
            "artifact_type": "PatchOperation",
            "kind": str(recipe.get("operation_kind") or "fallback_missing_registry_to_env"),
            "target": target,
            "file": path_text,
            "exception": patch["exception"],
            "fallback_function": patch["fallback_function"],
            "guarded_call_attribute": patch["guarded_call_attribute"],
        },
    )

def _timestamp_range_error_package(
    *, execution_dir: Path, project_dir: Path, target: str, path_text: str, symbol: str
) -> dict[str, Any]:
    recipe = timestamp_range_error_contract_recipe()
    if not recipe:
        return {**NO_PATCH, "reason": "timestamp_range_error_recipe_disabled"}
    sandbox_project = execution_dir / "patch_sandbox" / "project"
    _copy_project(project_dir, sandbox_project)
    source_path = (sandbox_project / path_text).resolve()
    try:
        source_path.relative_to(sandbox_project.resolve())
    except ValueError:
        return {"status": "blocked", "reason": "target_outside_sandbox", "patches": []}
    if not source_path.is_file():
        return {"status": "blocked", "reason": "target_file_missing_in_sandbox", "patches": []}
    original = source_path.read_text(encoding="utf-8")
    patch = timestamp_range_error_patch(original, symbol=symbol, recipe=recipe)
    if patch is None:
        return {**NO_PATCH, "reason": "timestamp_range_error_pattern_not_proven"}
    patched = str(patch["source"])
    source_path.write_text(patched, encoding="utf-8")
    return _patch_result(
        recipe=recipe,
        sandbox_project=sandbox_project,
        path_text=path_text,
        target=target,
        original=original,
        patched=patched,
        operation={
            "artifact_type": "PatchOperation",
            "kind": str(recipe.get("operation_kind") or "normalize_timestamp_range_error"),
            "target": target,
            "file": path_text,
            "exceptions": list(patch["exceptions"]),
            "message": patch["message"],
        },
    )

def _falsy_primitive_empty_package(
    *, execution_dir: Path, project_dir: Path, target: str, path_text: str, symbol: str
) -> dict[str, Any]:
    recipe = falsy_primitive_empty_contract_recipe()
    if not recipe:
        return {**NO_PATCH, "reason": "falsy_primitive_empty_recipe_disabled"}
    sandbox_project = execution_dir / "patch_sandbox" / "project"
    _copy_project(project_dir, sandbox_project)
    source_path = (sandbox_project / path_text).resolve()
    try:
        source_path.relative_to(sandbox_project.resolve())
    except ValueError:
        return {"status": "blocked", "reason": "target_outside_sandbox", "patches": []}
    if not source_path.is_file():
        return {"status": "blocked", "reason": "target_file_missing_in_sandbox", "patches": []}
    original = source_path.read_text(encoding="utf-8")
    patch = falsy_primitive_empty_patch(original, symbol=symbol, recipe=recipe)
    if patch is None:
        return {**NO_PATCH, "reason": "falsy_primitive_empty_pattern_not_proven"}
    patched = str(patch["source"])
    source_path.write_text(patched, encoding="utf-8")
    return _patch_result(
        recipe=recipe,
        sandbox_project=sandbox_project,
        path_text=path_text,
        target=target,
        original=original,
        patched=patched,
        operation={
            "artifact_type": "PatchOperation",
            "kind": str(recipe.get("operation_kind") or "preserve_falsy_primitive_override"),
            "target": target,
            "file": path_text,
            "candidate_parameter": patch["candidate_parameter"],
            "fallback_parameter": patch["fallback_parameter"],
        },
    )

def _incomplete_import_token_package(
    *, execution_dir: Path, project_dir: Path, target: str, path_text: str, symbol: str
) -> dict[str, Any]:
    recipe = incomplete_import_token_contract_recipe()
    if not recipe:
        return {**NO_PATCH, "reason": "incomplete_import_token_recipe_disabled"}
    sandbox_project = execution_dir / "patch_sandbox" / "project"
    _copy_project(project_dir, sandbox_project)
    source_path = (sandbox_project / path_text).resolve()
    try:
        source_path.relative_to(sandbox_project.resolve())
    except ValueError:
        return {"status": "blocked", "reason": "target_outside_sandbox", "patches": []}
    if not source_path.is_file():
        return {"status": "blocked", "reason": "target_file_missing_in_sandbox", "patches": []}
    original = source_path.read_text(encoding="utf-8")
    patch = incomplete_import_token_patch(original, symbol=symbol, recipe=recipe)
    if patch is None:
        return {**NO_PATCH, "reason": "incomplete_import_token_pattern_not_proven"}
    patched = str(patch["source"])
    source_path.write_text(patched, encoding="utf-8")
    return _patch_result(
        recipe=recipe,
        sandbox_project=sandbox_project,
        path_text=path_text,
        target=target,
        original=original,
        patched=patched,
        operation={
            "artifact_type": "PatchOperation",
            "kind": str(recipe.get("operation_kind") or "guard_incomplete_import_tokens"),
            "target": target,
            "file": path_text,
            "source_parameter": patch["source_parameter"],
            "indexed_token": patch["indexed_token"],
        },
    )

def _duplicate_cli_option_package(
    *, execution_dir: Path, project_dir: Path, target: str, path_text: str, symbol: str
) -> dict[str, Any]:
    recipe = duplicate_cli_short_option_contract_recipe()
    if not recipe:
        return {**NO_PATCH, "reason": "duplicate_cli_option_recipe_disabled"}
    sandbox_project = execution_dir / "patch_sandbox" / "project"
    _copy_project(project_dir, sandbox_project)
    source_path = (sandbox_project / path_text).resolve()
    try:
        source_path.relative_to(sandbox_project.resolve())
    except ValueError:
        return {"status": "blocked", "reason": "target_outside_sandbox", "patches": []}
    if not source_path.is_file():
        return {"status": "blocked", "reason": "target_file_missing_in_sandbox", "patches": []}
    original = source_path.read_text(encoding="utf-8")
    patch = duplicate_cli_option_patch(original, symbol=symbol, recipe=recipe)
    if patch is None:
        return {**NO_PATCH, "reason": "duplicate_cli_option_pattern_not_proven"}
    patched = str(patch["source"])
    source_path.write_text(patched, encoding="utf-8")
    return _patch_result(
        recipe=recipe,
        sandbox_project=sandbox_project,
        path_text=path_text,
        target=target,
        original=original,
        patched=patched,
        operation={
            "artifact_type": "PatchOperation",
            "kind": str(recipe.get("operation_kind") or "replace_duplicate_cli_short_option"),
            "target": target,
            "file": path_text,
            "option": patch["option"],
            "old_short_flag": patch["old_short_flag"],
            "new_short_flag": patch["new_short_flag"],
        },
    )

def _strict_default_comparison_package(
    *, execution_dir: Path, project_dir: Path, target: str, path_text: str, symbol: str
) -> dict[str, Any]:
    recipe = strict_default_string_comparison_contract_recipe()
    if not recipe:
        return {**NO_PATCH, "reason": "strict_default_comparison_recipe_disabled"}
    sandbox_project = execution_dir / "patch_sandbox" / "project"
    _copy_project(project_dir, sandbox_project)
    source_path = (sandbox_project / path_text).resolve()
    try:
        source_path.relative_to(sandbox_project.resolve())
    except ValueError:
        return {"status": "blocked", "reason": "target_outside_sandbox", "patches": []}
    if not source_path.is_file():
        return {"status": "blocked", "reason": "target_file_missing_in_sandbox", "patches": []}
    original = source_path.read_text(encoding="utf-8")
    patch = strict_default_comparison_patch(original, symbol=symbol, recipe=recipe)
    if patch is None:
        return {**NO_PATCH, "reason": "strict_default_comparison_pattern_not_proven"}
    patched = str(patch["source"])
    source_path.write_text(patched, encoding="utf-8")
    return _patch_result(
        recipe=recipe,
        sandbox_project=sandbox_project,
        path_text=path_text,
        target=target,
        original=original,
        patched=patched,
        operation={
            "artifact_type": "PatchOperation",
            "kind": str(recipe.get("operation_kind") or "guard_empty_string_comparison_type"),
            "target": target,
            "file": path_text,
            "value_name": patch["value_name"],
        },
    )

def _fstring_brace_offset_package(
    *, execution_dir: Path, project_dir: Path, target: str, path_text: str, symbol: str
) -> dict[str, Any]:
    recipe = escaped_fstring_brace_offset_contract_recipe()
    if not recipe:
        return {**NO_PATCH, "reason": "fstring_brace_offset_recipe_disabled"}
    sandbox_project = execution_dir / "patch_sandbox" / "project"
    _copy_project(project_dir, sandbox_project)
    source_path = (sandbox_project / path_text).resolve()
    try:
        source_path.relative_to(sandbox_project.resolve())
    except ValueError:
        return {"status": "blocked", "reason": "target_outside_sandbox", "patches": []}
    if not source_path.is_file():
        return {"status": "blocked", "reason": "target_file_missing_in_sandbox", "patches": []}
    original = source_path.read_text(encoding="utf-8")
    patch = fstring_brace_offset_patch(original, symbol=symbol, recipe=recipe)
    if patch is None:
        return {**NO_PATCH, "reason": "fstring_brace_offset_pattern_not_proven"}
    patched = str(patch["source"])
    source_path.write_text(patched, encoding="utf-8")
    return _patch_result(
        recipe=recipe,
        sandbox_project=sandbox_project,
        path_text=path_text,
        target=target,
        original=original,
        patched=patched,
        operation={
            "artifact_type": "PatchOperation",
            "kind": str(recipe.get("operation_kind") or "adjust_fstring_middle_brace_offsets"),
            "target": target,
            "file": path_text,
            "offset_name": patch["offset_name"],
        },
    )

def _trailing_backslash_bounds_package(
    *, execution_dir: Path, project_dir: Path, target: str, path_text: str, symbol: str
) -> dict[str, Any]:
    recipe = trailing_backslash_bounds_contract_recipe()
    if not recipe:
        return {**NO_PATCH, "reason": "trailing_backslash_bounds_recipe_disabled"}
    sandbox_project = execution_dir / "patch_sandbox" / "project"
    _copy_project(project_dir, sandbox_project)
    source_path = (sandbox_project / path_text).resolve()
    try:
        source_path.relative_to(sandbox_project.resolve())
    except ValueError:
        return {"status": "blocked", "reason": "target_outside_sandbox", "patches": []}
    if not source_path.is_file():
        return {"status": "blocked", "reason": "target_file_missing_in_sandbox", "patches": []}
    original = source_path.read_text(encoding="utf-8")
    patch = trailing_backslash_bounds_patch(original, symbol=symbol, recipe=recipe)
    if patch is None:
        return {**NO_PATCH, "reason": "trailing_backslash_bounds_pattern_not_proven"}
    patched = str(patch["source"])
    source_path.write_text(patched, encoding="utf-8")
    return _patch_result(
        recipe=recipe,
        sandbox_project=sandbox_project,
        path_text=path_text,
        target=target,
        original=original,
        patched=patched,
        operation={
            "artifact_type": "PatchOperation",
            "kind": str(recipe.get("operation_kind") or "guard_trailing_backslash_index"),
            "target": target,
            "file": path_text,
            "index_name": patch["index_name"],
            "count_name": patch["count_name"],
        },
    )

def _framework_contract_package(
    *, execution_dir: Path, project_dir: Path, target: str, path_text: str,
    symbol: str, operation_kind: str,
) -> dict[str, Any]:
    recipe = framework_contract_recipe(operation_kind)
    if not recipe:
        return {**NO_PATCH, "reason": "framework_contract_recipe_disabled"}
    sandbox_project = execution_dir / "patch_sandbox" / "project"
    _copy_project(project_dir, sandbox_project)
    source_path = (sandbox_project / path_text).resolve()
    try:
        source_path.relative_to(sandbox_project.resolve())
    except ValueError:
        return {"status": "blocked", "reason": "target_outside_sandbox", "patches": []}
    if not source_path.is_file():
        return {"status": "blocked", "reason": "target_file_missing_in_sandbox", "patches": []}
    original = source_path.read_text(encoding="utf-8")
    patch = framework_contract_patch(
        original, symbol=symbol, operation_kind=operation_kind, recipe=recipe
    )
    if patch is None:
        return {**NO_PATCH, "reason": "framework_contract_pattern_not_proven"}
    patched = str(patch["source"])
    source_path.write_text(patched, encoding="utf-8")
    return _patch_result(
        recipe=recipe,
        sandbox_project=sandbox_project,
        path_text=path_text,
        target=target,
        original=original,
        patched=patched,
        operation={
            "artifact_type": "PatchOperation",
            "kind": operation_kind,
            "target": target,
            "file": path_text,
        },
    )
