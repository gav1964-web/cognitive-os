"""Bounded recovery-route patch package synthesis."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .patch_synthesis_policy import (
    append_mapping_helper_recipe,
    development_helper_extraction_recipe,
    json_dumps_helper_recipe,
    json_loads_helper_recipe,
    splitlines_helper_recipe,
)
from .programmer_patch_synthesizer_common import NO_PATCH, _copy_project, _patch_result, _recovery_patch_digest
from .programmer_patch_synthesizer_helper_extractors import (
    _extract_append_mapping_helper,
    _extract_json_dumps_helper,
    _extract_json_loads_helper,
    _extract_splitlines_helper,
)

def synthesize_recovery_patch_package(
    *,
    execution_dir: Path,
    project_dir: Path,
    recovery_route: dict[str, Any],
) -> dict[str, Any]:
    """Prepare a source-preserving decomposition in an isolated sandbox."""
    hypothesis = dict(recovery_route.get("research_hypothesis") or {})
    gate = dict(recovery_route.get("architect_reentry_gate") or {})
    proposed = str(hypothesis.get("proposed_target") or "")
    origin = str(hypothesis.get("origin_target") or "")
    proposed_path, _, proposed_symbol = proposed.partition(":")
    recipes = (
        append_mapping_helper_recipe(),
        json_dumps_helper_recipe(),
        json_loads_helper_recipe(),
        splitlines_helper_recipe(),
    )
    recipe = next(
        (row for row in recipes if row and proposed_symbol == row.get("required_candidate_symbol")),
        {},
    )
    if (
        not recipe
        or recovery_route.get("status") != "bounded_rework_ready"
        or gate.get("status") != "accepted_for_bounded_rework"
    ):
        return {**NO_PATCH, "reason": "recovery_route_not_admitted"}
    allowed_type = str(recipe.get("allowed_hypothesis_type") or "")
    if hypothesis.get("hypothesis_type") != allowed_type:
        return {**NO_PATCH, "reason": "recovery_hypothesis_not_supported"}
    origin_path, _, origin_symbol = origin.partition(":")
    if (
        not origin_symbol
        or origin_path != proposed_path
        or proposed_symbol != recipe.get("required_candidate_symbol")
        or not origin_path.endswith(".py")
    ):
        return {**NO_PATCH, "reason": "recovery_target_contract_mismatch"}

    sandbox_project = execution_dir / "recovery_patch_sandbox" / "project"
    _copy_project(project_dir, sandbox_project)
    source_path = (sandbox_project / origin_path).resolve()
    try:
        source_path.relative_to(sandbox_project.resolve())
    except ValueError:
        return {"status": "blocked", "reason": "target_outside_sandbox", "patches": []}
    if not source_path.is_file():
        return {"status": "blocked", "reason": "target_file_missing_in_sandbox", "patches": []}
    original_bytes = source_path.read_bytes()
    original = original_bytes.decode("utf-8")
    source_precondition_sha256 = hashlib.sha256(original_bytes).hexdigest()
    operation_kind = str(recipe.get("operation_kind") or "")
    if operation_kind == "extract_append_mapping_helper":
        patch = _extract_append_mapping_helper(
            original,
            origin_symbol=origin_symbol,
            proposed_symbol=proposed_symbol,
            maximum_mapping_fields=int(recipe.get("maximum_mapping_fields") or 12),
        )
        operation_details = ({
            "loop_variable": patch["loop_variable"],
            "accumulator": patch["accumulator"],
            "mapping_field_count": patch["mapping_field_count"],
            "mapping_source": patch["mapping_source"],
        } if patch else {})
        pattern_reason = "append_mapping_helper_pattern_not_proven"
    elif operation_kind == "extract_json_dumps_helper":
        patch = _extract_json_dumps_helper(
            original,
            origin_symbol=origin_symbol,
            proposed_symbol=proposed_symbol,
            maximum_free_variables=int(recipe.get("maximum_free_variables") or 1),
        )
        operation_details = ({
            "free_variable": patch["free_variable"],
            "serialization_line": patch["serialization_line"],
        } if patch else {})
        pattern_reason = "json_dumps_helper_pattern_not_proven"
    elif operation_kind == "extract_json_loads_helper":
        patch = _extract_json_loads_helper(
            original,
            origin_symbol=origin_symbol,
            proposed_symbol=proposed_symbol,
        )
        operation_details = ({
            "read_expression": patch["read_expression"],
            "parse_line": patch["parse_line"],
        } if patch else {})
        pattern_reason = "json_loads_helper_pattern_not_proven"
    elif operation_kind == "extract_splitlines_helper":
        patch = _extract_splitlines_helper(
            original,
            origin_symbol=origin_symbol,
            proposed_symbol=proposed_symbol,
        )
        operation_details = ({
            "text_expression": patch["text_expression"],
            "split_line": patch["split_line"],
        } if patch else {})
        pattern_reason = "splitlines_helper_pattern_not_proven"
    else:
        return {**NO_PATCH, "reason": "unsupported_recovery_patch_recipe"}
    if patch is None:
        return {**NO_PATCH, "reason": pattern_reason}
    patched = patch["source"]
    try:
        compile(patched, origin_path, "exec")
    except SyntaxError:
        return {"status": "blocked", "reason": "synthesized_source_does_not_compile", "patches": []}
    source_path.write_bytes(patched.encode("utf-8"))
    result = _patch_result(
        recipe=recipe,
        sandbox_project=sandbox_project,
        path_text=origin_path,
        target=origin,
        original=original,
        patched=patched,
        operation={
            "artifact_type": "PatchOperation",
            "kind": operation_kind,
            "target": origin,
            "file": origin_path,
            "created_target": proposed,
            **operation_details,
        },
    )
    return {
        "artifact_type": "RecoveryPatchPackage",
        **result,
        "source_precondition_sha256": source_precondition_sha256,
        "patched_source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "patch_digest": _recovery_patch_digest(result["patches"], source_precondition_sha256),
        "source_code_changes": False,
        "registry_changes": False,
        "verification": {
            "patched_source_compiles": True,
            "sandbox_only": True,
            "normal_architect_reselection_pending": True,
        },
        "policy": {
            "automatic_source_mutation_allowed": False,
            "apply_source_enabled": False,
            "required_verification": list(recipe.get("required_verification") or []),
        },
    }

def _development_helper_extraction_package(
    *,
    execution_dir: Path,
    project_dir: Path,
    target: str,
    path_text: str,
    operation_kinds: list[str],
) -> dict[str, Any]:
    prepared: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    for index, operation_kind in enumerate(dict.fromkeys(operation_kinds)):
        recipe = development_helper_extraction_recipe(operation_kind)
        if not recipe:
            return {**NO_PATCH, "reason": "unsupported_development_helper_extraction"}
        proposed_symbol = str(recipe.get("required_candidate_symbol") or "")
        if not proposed_symbol:
            return {**NO_PATCH, "reason": "development_helper_symbol_missing"}
        package = synthesize_recovery_patch_package(
            execution_dir=execution_dir / "development_helper_candidates" / str(index),
            project_dir=project_dir,
            recovery_route={
                "status": "bounded_rework_ready",
                "research_hypothesis": {
                    "hypothesis_type": recipe.get("allowed_hypothesis_type"),
                    "origin_target": target,
                    "proposed_target": f"{path_text}:{proposed_symbol}",
                },
                "architect_reentry_gate": {"status": "accepted_for_bounded_rework"},
            },
        )
        attempts.append({
            "operation_kind": operation_kind,
            "status": package.get("status"),
            "reason": package.get("reason"),
        })
        if package.get("status") == "prepared":
            prepared.append(package)
    if len(prepared) == 1:
        return {**prepared[0], "reducer_selection": {"status": "unique", "attempts": attempts}}
    reason = (
        "ambiguous_development_helper_extraction"
        if len(prepared) > 1
        else attempts[0]["reason"] if len(attempts) == 1 else "no_unique_development_helper_extraction"
    )
    return {**NO_PATCH, "reason": reason, "reducer_selection": {"status": "blocked", "attempts": attempts}}
