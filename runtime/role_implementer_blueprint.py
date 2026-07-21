"""Executor-facing contracts emitted by the Implementer role."""

from __future__ import annotations

from typing import Any


def build_implementation_blueprint(
    *,
    target: dict[str, Any],
    binding: dict[str, Any],
    change_plan: list[dict[str, Any]],
    quality_gates: list[dict[str, Any]],
    acceptance: list[dict[str, Any]],
) -> dict[str, Any]:
    candidate = target.get("candidate")
    if not candidate:
        return {
            "artifact_type": "ImplementationBlueprint",
            "status": "blocked_no_safe_candidate",
            "target": None,
            "reason": target.get("selection_reason") or "no source-backed implementation target",
        }
    return {
        "artifact_type": "ImplementationBlueprint",
        "status": "ready",
        "target": candidate,
        "language": "python",
        "operation": "modify_existing_symbol_or_extract_adjacent_helper",
        "source_contract": {
            "input_contract": binding.get("input_contract", {}),
            "output_contract": binding.get("output_contract", {}),
            "side_effects": binding.get("side_effects", {}),
            "binding_status": binding.get("binding_status"),
        },
        "edit_strategy": [
            "read target source and neighboring callers before editing",
            "preserve public API unless TechnicalSpec explicitly requires a contract change",
            "keep helper extraction adjacent to the target symbol when possible",
            "prefer deterministic code over new runtime dependencies",
            "bind each code delta to a change_plan item and quality gate",
        ],
        "change_plan_ids": _ids(change_plan),
        "quality_gate_ids": _ids(quality_gates),
        "acceptance_binding": _acceptance_ids(acceptance),
        "completion_signal": "PatchPackage plus TestResult can be consumed by Reviewer without extra interpretation.",
    }


def build_patch_intent(
    *,
    target: dict[str, Any],
    writable_scope: list[str],
    expected_files: list[str],
    verification_commands: list[str],
) -> dict[str, Any]:
    candidate = target.get("candidate")
    return {
        "artifact_type": "PatchIntent",
        "mode": "sandbox_first",
        "status": "ready" if candidate else "blocked_no_safe_candidate",
        "target_symbol": candidate,
        "allowed_files": expected_files,
        "allowed_write_scope": writable_scope,
        "required_patch_package_sections": ["summary", "patches", "verification", "rollback", "known_limits"],
        "verification_commands": verification_commands,
        "apply_source_default": False,
        "source_edit_requires_human_approval": True,
    }


def build_executor_handoff(*, patch_intent: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_type": "ExecutorHandoff",
        "recommended_tool": "tools/apply_implementation_plan.py",
        "executor": "programmer_executor",
        "inputs": ["TechnicalSpec", "ImplementationPlan", "TestPlan"],
        "patch_intent_mode": patch_intent.get("mode"),
        "apply_source_default": False,
        "run_verification_default": True,
        "expected_outputs": ["PatchPackage", "TestResult", "Reviewer handoff"],
        "blocked_if": [
            "ImplementationPlan.implementation_target.status == blocked_no_safe_candidate",
            "PatchIntent.allowed_files is empty",
            "requested change leaves PatchIntent.allowed_write_scope",
        ],
    }


def _ids(rows: list[dict[str, Any]]) -> list[str]:
    return [str(row.get("id")) for row in rows if isinstance(row, dict) and row.get("id")]


def _acceptance_ids(rows: list[dict[str, Any]]) -> list[str]:
    return [str(row.get("id")) for row in rows[:10] if isinstance(row, dict) and row.get("id")]
