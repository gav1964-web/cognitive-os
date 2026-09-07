"""Patch synthesis router for deterministic programmer operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .patch_synthesis_policy import (
    required_input_guard_recipe,
    return_literal_notimplemented_recipe,
    return_literal_stub_recipe,
    string_transform_identity_return_recipe,
)
from .programmer_contract_transform_patch import contract_transform_patch
from .programmer_literal_stub_patch import literal_return_patch, notimplemented_return_patch
from .programmer_patch_synthesizer_common import NO_PATCH, _copy_project, _expected_files, _patch_result, _target_symbol
from .programmer_patch_synthesizer_contract_packages import (
    _duplicate_cli_option_package,
    _framework_contract_package,
    _falsy_primitive_empty_package,
    _fstring_brace_offset_package,
    _incomplete_import_token_package,
    _registry_fallback_package,
    _strict_default_comparison_package,
    _timestamp_range_error_package,
    _trailing_backslash_bounds_package,
)
from .programmer_patch_synthesizer_guard import (
    _guard_evidence,
    _guard_required_keys,
    _patch_required_input_guard,
    _required_input_keys,
    _required_signature_keys,
)
from .programmer_patch_synthesizer_recovery import _development_helper_extraction_package
from .programmer_patch_synthesizer_training import training_repair_package

TRAINING_REPAIR_OPERATORS = {
    "guard_empty_materialized_fast_path",
    "require_left_token_boundary_for_numeric_range",
}

def synthesize_patch_package(
    *,
    execution_dir: Path,
    project_dir: Path,
    implementation_plan: dict[str, Any],
    test_plan: dict[str, Any],
) -> dict[str, Any]:
    delta = dict(implementation_plan.get("implementation_delta") or {})
    if delta.get("status") == "verification_only":
        return {
            "status": "verification_only",
            "reason": "no_evidence_backed_behavior_change",
            "patches": [],
            "implementation_delta": delta,
        }
    if delta.get("status") == "semantic_synthesis_required":
        return {
            "status": "skipped",
            "reason": "semantic_delta_requires_patch_hypothesis",
            "patches": [],
            "implementation_delta": delta,
        }
    target = _target_symbol(implementation_plan)
    if not target:
        return dict(NO_PATCH)
    path_text, _, symbol = target.partition(":")
    if not path_text.endswith(".py") or not symbol:
        return dict(NO_PATCH)
    if path_text not in _expected_files(implementation_plan):
        return {"status": "blocked", "reason": "target_file_not_in_expected_files", "patches": []}
    intent = dict(delta.get("intent") or {})
    operation_kind = str(intent.get("operator_id") or "")
    allowed_operations = [str(value) for value in intent.get("allowed_operator_ids") or [] if value]
    if operation_kind in TRAINING_REPAIR_OPERATORS:
        if intent.get("authority") != "explicit_training_replay" or allowed_operations != [operation_kind]:
            return {"status": "blocked", "reason": "training_replay_authority_required", "patches": []}
        return training_repair_package(
            execution_dir=execution_dir, project_dir=project_dir, target=target,
            path_text=path_text, symbol=symbol, operation_kind=operation_kind,
        )
    if operation_kind.startswith("extract_") or allowed_operations:
        if allowed_operations in (
            ["fallback_missing_registry_to_env"],
            ["normalize_timestamp_range_error"],
            ["preserve_falsy_primitive_override"],
            ["guard_incomplete_import_tokens"],
            ["replace_duplicate_cli_short_option"],
            ["guard_empty_string_comparison_type"],
            ["adjust_fstring_middle_brace_offsets"],
            ["guard_trailing_backslash_index"],
            ["guard_empty_theme_config"],
            ["order_extra_hooks_after_wrappers"],
            ["derive_dist_info_from_wheel_contents"],
        ):
            operation_kind = allowed_operations[0]
        else:
            return _development_helper_extraction_package(
                execution_dir=execution_dir,
                project_dir=project_dir,
                target=target,
                path_text=path_text,
                operation_kinds=allowed_operations or [operation_kind],
            )
    if operation_kind == "fallback_missing_registry_to_env":
        return _registry_fallback_package(
            execution_dir=execution_dir,
            project_dir=project_dir,
            target=target,
            path_text=path_text,
            symbol=symbol,
        )
    if operation_kind == "normalize_timestamp_range_error":
        return _timestamp_range_error_package(
            execution_dir=execution_dir,
            project_dir=project_dir,
            target=target,
            path_text=path_text,
            symbol=symbol,
        )
    if operation_kind == "preserve_falsy_primitive_override":
        return _falsy_primitive_empty_package(
            execution_dir=execution_dir,
            project_dir=project_dir,
            target=target,
            path_text=path_text,
            symbol=symbol,
        )
    if operation_kind == "guard_incomplete_import_tokens":
        return _incomplete_import_token_package(
            execution_dir=execution_dir,
            project_dir=project_dir,
            target=target,
            path_text=path_text,
            symbol=symbol,
        )
    if operation_kind == "replace_duplicate_cli_short_option":
        return _duplicate_cli_option_package(
            execution_dir=execution_dir,
            project_dir=project_dir,
            target=target,
            path_text=path_text,
            symbol=symbol,
        )
    if operation_kind == "guard_empty_string_comparison_type":
        return _strict_default_comparison_package(
            execution_dir=execution_dir,
            project_dir=project_dir,
            target=target,
            path_text=path_text,
            symbol=symbol,
        )
    if operation_kind == "adjust_fstring_middle_brace_offsets":
        return _fstring_brace_offset_package(
            execution_dir=execution_dir,
            project_dir=project_dir,
            target=target,
            path_text=path_text,
            symbol=symbol,
        )
    if operation_kind == "guard_trailing_backslash_index":
        return _trailing_backslash_bounds_package(
            execution_dir=execution_dir,
            project_dir=project_dir,
            target=target,
            path_text=path_text,
            symbol=symbol,
        )
    if operation_kind in {
        "guard_empty_theme_config",
        "order_extra_hooks_after_wrappers",
        "derive_dist_info_from_wheel_contents",
    }:
        return _framework_contract_package(
            execution_dir=execution_dir,
            project_dir=project_dir,
            target=target,
            path_text=path_text,
            symbol=symbol,
            operation_kind=operation_kind,
        )
    if "." in symbol:
        return dict(NO_PATCH)
    if operation_kind.startswith("extract_"):
        return _development_helper_extraction_package(
            execution_dir=execution_dir,
            project_dir=project_dir,
            target=target,
            path_text=path_text,
            operation_kinds=allowed_operations or [operation_kind],
        )
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
    transform_recipe = string_transform_identity_return_recipe()
    if transform_recipe:
        patch = contract_transform_patch(original, symbol, target, path_text, test_plan, transform_recipe)
        if patch:
            source.write_text(patch["source"], encoding="utf-8")
            return _patch_result(
                recipe=transform_recipe,
                sandbox_project=sandbox_project,
                path_text=path_text,
                target=target,
                original=original,
                patched=str(patch["source"]),
                operation={
                    "artifact_type": "PatchOperation",
                    "kind": str(transform_recipe.get("operation_kind") or "replace_identity_return_with_contract_transform"),
                    "target": target,
                    "file": path_text,
                    "transform": patch["transform"],
                    "transform_evidence": patch["transform_evidence"],
                },
            )
    literal_recipe = return_literal_stub_recipe()
    if literal_recipe:
        literal_patch = literal_return_patch(original, symbol, target, path_text, test_plan, literal_recipe)
        if literal_patch:
            source.write_text(literal_patch["source"], encoding="utf-8")
            return _patch_result(
                recipe=literal_recipe,
                sandbox_project=sandbox_project,
                path_text=path_text,
                target=target,
                original=original,
                patched=str(literal_patch["source"]),
                operation={
                    "artifact_type": "PatchOperation",
                    "kind": str(literal_recipe.get("operation_kind") or "replace_stub_with_literal_return"),
                    "target": target,
                    "file": path_text,
                    "return_value": literal_patch["return_value"],
                    "return_evidence": literal_patch["return_evidence"],
                },
            )
    notimplemented_recipe = return_literal_notimplemented_recipe()
    if notimplemented_recipe:
        patch = notimplemented_return_patch(original, symbol, target, path_text, test_plan, notimplemented_recipe)
        if patch:
            source.write_text(patch["source"], encoding="utf-8")
            return _patch_result(
                recipe=notimplemented_recipe,
                sandbox_project=sandbox_project,
                path_text=path_text,
                target=target,
                original=original,
                patched=str(patch["source"]),
                operation={
                    "artifact_type": "PatchOperation",
                    "kind": str(notimplemented_recipe.get("operation_kind") or "replace_notimplemented_with_literal_return"),
                    "target": target,
                    "file": path_text,
                    "return_value": patch["return_value"],
                    "return_evidence": patch["return_evidence"],
                },
            )
    signature_keys = _required_signature_keys(original, symbol, recipe)
    contract_keys = _required_input_keys(test_plan, target, recipe)
    required_keys = contract_keys or signature_keys
    if not required_keys:
        return dict(NO_PATCH)
    guard_keys = _guard_required_keys(original, symbol, required_keys)
    if not guard_keys and signature_keys and required_keys != signature_keys:
        guard_keys = _guard_required_keys(original, symbol, signature_keys)
        required_keys = signature_keys
    if not guard_keys:
        return dict(NO_PATCH)
    patched = _patch_required_input_guard(original, symbol, guard_keys, recipe)
    if patched == original:
        return dict(NO_PATCH)
    source.write_text(patched, encoding="utf-8")
    return _patch_result(
        recipe=recipe,
        sandbox_project=sandbox_project,
        path_text=path_text,
        target=target,
        original=original,
        patched=patched,
        operation={
            "artifact_type": "PatchOperation",
            "kind": str(recipe.get("operation_kind") or "insert_required_input_guard"),
            "target": target,
            "file": path_text,
            "required_inputs": guard_keys,
            "guard_evidence": _guard_evidence(contract_keys, signature_keys, guard_keys),
        },
    )
