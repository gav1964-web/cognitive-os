"""Implementer curriculum evaluator for teacher-reference projects."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .configured_role_pipeline import artifact_by_type, producer_for_artifact_type, run_configured_role_prefix
from .project_benchmark import analyze_project


REFERENCE_QUALITY = "teacher_reference_not_ground_truth"
IMPROVEMENT_PROTOCOL = "external_teacher_corrector_loop"


def run_implementer_curriculum(
    *,
    root: Path,
    curriculum_dir: Path,
    write: bool = False,
) -> dict[str, Any]:
    cases = [run_curriculum_case(root=root, reference_path=path) for path in _reference_paths(curriculum_dir)]
    report = _report(cases, curriculum_dir=curriculum_dir)
    if write:
        out_dir = root / "artifacts" / "curricula"
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = out_dir / f"implementer_curriculum_{stamp}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = path.as_posix()
    return report


def run_curriculum_case(*, root: Path, reference_path: Path) -> dict[str, Any]:
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    _validate_teacher_reference(reference_path, reference)
    project_dir = _resolve_project_dir(root, reference_path, reference)
    project_report = analyze_project(project_dir)["project_map_report"]
    artifacts = run_configured_role_prefix(
        goal=f"Implementer curriculum pass for {reference_path.parent.name}",
        project_report=project_report,
        until_artifact_type="ImplementationPlan",
    )
    plan = artifact_by_type(artifacts, "ImplementationPlan")
    actual = _actual_plan(plan)
    score = _score_plan(dict(reference.get("expected_plan", {})), actual)
    backlog = _improvement_backlog(score)
    passed = score["score"] >= 0.9 and not backlog
    return {
        "case": reference_path.parent.name,
        "project_dir": project_dir.as_posix(),
        "status": "ok" if passed else "needs_improvement",
        "score": score,
        "teacher_reference": {
            "reference_quality": reference.get("reference_quality"),
            "teacher_profile": reference.get("teacher_profile"),
            "improvement_protocol": IMPROVEMENT_PROTOCOL,
        },
        "actual": actual,
        "teacher_review": _teacher_review(reference.get("teacher_review", {}), backlog),
        "improvement_backlog": backlog,
    }


def _actual_plan(plan: dict[str, Any]) -> dict[str, Any]:
    target = dict(plan.get("implementation_target", {}))
    binding = dict(plan.get("contract_binding", {}))
    rollback = dict(plan.get("rollback_plan", {}))
    next_artifact = dict(plan.get("next_artifact", {}))
    patch_package = dict(plan.get("patch_package_contract", {}))
    debug_rework = dict(plan.get("debug_rework_policy", {}))
    blueprint = dict(plan.get("implementation_blueprint", {}))
    patch_intent = dict(plan.get("patch_intent", {}))
    executor_handoff = dict(plan.get("executor_handoff", {}))
    return {
        "artifact_type": plan.get("artifact_type"),
        "role": plan.get("role"),
        "candidate": target.get("candidate"),
        "binding_candidate": binding.get("candidate"),
        "binding_status": binding.get("binding_status"),
        "has_input_contract": bool(binding.get("input_contract")),
        "has_output_contract": bool(binding.get("output_contract")),
        "patch_scope": _strings(plan.get("patch_scope", [])),
        "evidence_scope": _strings(plan.get("evidence_scope", [])),
        "writable_scope": _strings(plan.get("writable_scope", [])),
        "expected_files": _strings(plan.get("expected_files", [])),
        "rollback_files": _strings(rollback.get("files", [])),
        "registry_policy": rollback.get("registry_policy"),
        "verification_commands": _strings(plan.get("verification_commands", [])),
        "implementation_step_ids": _sources(plan.get("implementation_steps", []), key="id"),
        "implementation_actions": _sources(plan.get("implementation_steps", []), key="action"),
        "implementation_unit_count": len(plan.get("implementation_units", []) if isinstance(plan.get("implementation_units"), list) else []),
        "change_plan_count": len(plan.get("change_plan", []) if isinstance(plan.get("change_plan"), list) else []),
        "quality_gate_count": len(plan.get("quality_gates", []) if isinstance(plan.get("quality_gates"), list) else []),
        "implementation_blueprint_type": blueprint.get("artifact_type"),
        "implementation_blueprint_status": blueprint.get("status"),
        "implementation_blueprint_target": blueprint.get("target"),
        "patch_intent_type": patch_intent.get("artifact_type"),
        "patch_intent_mode": patch_intent.get("mode"),
        "patch_intent_target": patch_intent.get("target_symbol"),
        "patch_intent_apply_source_default": patch_intent.get("apply_source_default"),
        "executor_handoff_type": executor_handoff.get("artifact_type"),
        "executor_handoff_tool": executor_handoff.get("recommended_tool"),
        "executor_handoff_apply_source_default": executor_handoff.get("apply_source_default"),
        "patch_package_artifact_type": patch_package.get("artifact_type"),
        "patch_package_apply_policy": patch_package.get("apply_policy"),
        "dependency_policy": dict(plan.get("dependency_policy", {})).get("new_runtime_dependencies"),
        "debug_rework_output": debug_rework.get("output_artifact"),
        "debug_rework_max_attempts": debug_rework.get("max_attempts"),
        "acceptance_mapping_count": len(plan.get("acceptance_mapping", []) if isinstance(plan.get("acceptance_mapping"), list) else []),
        "non_goals": _strings(plan.get("non_goals", [])),
        "forbidden_actions_observed": _strings(plan.get("forbidden_actions_observed", [])),
        "next_role": next_artifact.get("recommended_role"),
    }


def _score_plan(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    plan_producer = producer_for_artifact_type("ImplementationPlan")
    test_producer = producer_for_artifact_type("TestPlan")
    checks = {
        "artifact_is_implementation_plan": actual.get("artifact_type") == "ImplementationPlan" and actual.get("role") == plan_producer,
        "candidate_matches": actual.get("candidate") == expected.get("candidate"),
        "binding_targets_candidate": actual.get("binding_candidate") == actual.get("candidate"),
        "bound_to_extraction_contract": actual.get("binding_status") == "bound_to_extraction_contract",
        "has_input_contract": actual.get("has_input_contract") is True,
        "has_output_contract": actual.get("has_output_contract") is True,
        "required_patch_scope_covered": _expected_covered(expected.get("patch_scope", []), actual.get("patch_scope", [])),
        "required_evidence_scope_covered": _expected_covered(
            expected.get("evidence_scope", expected.get("patch_scope", [])),
            actual.get("evidence_scope", []),
        ),
        "writable_scope_targets_candidate": actual.get("writable_scope") == _strings(expected.get("writable_scope", [expected.get("candidate")])),
        "required_expected_files_covered": _expected_covered(expected.get("expected_files", []), actual.get("expected_files", [])),
        "rollback_files_cover_expected_files": _expected_covered(actual.get("expected_files", []), actual.get("rollback_files", [])),
        "verification_commands_covered": _expected_covered(expected.get("verification_commands", []), actual.get("verification_commands", [])),
        "implementation_units_present": int(actual.get("implementation_unit_count") or 0) >= 1,
        "change_plan_present": int(actual.get("change_plan_count") or 0) >= 3,
        "quality_gates_present": int(actual.get("quality_gate_count") or 0) >= 3,
        "implementation_blueprint_present": actual.get("implementation_blueprint_type") == "ImplementationBlueprint"
        and actual.get("implementation_blueprint_status") == "ready"
        and actual.get("implementation_blueprint_target") == actual.get("candidate"),
        "patch_intent_sandbox_first": actual.get("patch_intent_type") == "PatchIntent"
        and actual.get("patch_intent_mode") == "sandbox_first"
        and actual.get("patch_intent_target") == actual.get("candidate")
        and actual.get("patch_intent_apply_source_default") is False,
        "executor_handoff_present": actual.get("executor_handoff_type") == "ExecutorHandoff"
        and actual.get("executor_handoff_tool") == "tools/apply_implementation_plan.py"
        and actual.get("executor_handoff_apply_source_default") is False,
        "patch_package_contract_present": actual.get("patch_package_artifact_type") == "PatchPackage",
        "patch_package_requires_human_apply": "human approval" in str(actual.get("patch_package_apply_policy") or "").lower(),
        "dependency_policy_conservative": actual.get("dependency_policy") == "forbidden_by_default",
        "debug_rework_policy_present": actual.get("debug_rework_output") == "BoundedReworkPlan"
        and int(actual.get("debug_rework_max_attempts") or 0) >= 1,
        "required_non_goals_covered": _expected_covered(expected.get("required_non_goals", []), actual.get("non_goals", [])),
        "acceptance_mapping_present": int(actual.get("acceptance_mapping_count") or 0) >= int(expected.get("min_acceptance_mapping_count", 1)),
        "no_forbidden_actions_observed": not actual.get("forbidden_actions_observed"),
        "registry_policy_protects_registry": "do not edit registry" in str(actual.get("registry_policy") or "").lower(),
        "next_role_targets_next_configured_producer": actual.get("next_role") == test_producer,
    }
    warnings = [name for name, ok in checks.items() if not ok]
    return {"score": _ratio(sum(1 for ok in checks.values() if ok), len(checks)), "checks": checks, "warnings": warnings}


def _report(cases: list[dict[str, Any]], *, curriculum_dir: Path) -> dict[str, Any]:
    passed = sum(1 for case in cases if case["status"] == "ok")
    milestone = "Implementer Curriculum External-3 v0.1" if "external" in curriculum_dir.name else "Implementer Curriculum Local-3 v0.1"
    return {
        "status": "ok" if passed == len(cases) else "needs_improvement",
        "milestone": milestone,
        "generated_at": _now(),
        "project_count": len(cases),
        "passed": passed,
        "summary": {
            "score": _ratio(sum(case["score"]["score"] for case in cases), len(cases)),
            "backlog_items": sum(len(case["improvement_backlog"]) for case in cases),
        },
        "invariants": {
            "teacher_reference_is_ground_truth": False,
            "improvement_protocol": IMPROVEMENT_PROTOCOL,
            "facts_and_judgments_scored_separately": True,
            "automatic_code_changes_from_own_output": False,
            "source_code_changes": False,
            "registry_changes": False,
            "foundry_or_promote_not_in_scope": True,
            "tester_reviewer_not_in_scope": True,
        },
        "cases": cases,
    }


def _improvement_backlog(score: dict[str, Any]) -> list[dict[str, str]]:
    return [{"type": "IMPLEMENTER_GAP", "check": warning} for warning in score["warnings"]]


def _teacher_review(value: Any, backlog: list[dict[str, str]]) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {
        "project_condition": value.get("project_condition", ""),
        "expected_plan_behavior": _strings(value.get("expected_plan_behavior", [])),
        "known_risks": _strings(value.get("known_risks", [])),
        "status": "watch" if backlog else "covered_by_current_run",
    }


def _validate_teacher_reference(reference_path: Path, reference: dict[str, Any]) -> None:
    if reference.get("reference_quality") != REFERENCE_QUALITY:
        raise ValueError(f"{reference_path} must declare reference_quality={REFERENCE_QUALITY!r}")
    if not isinstance(reference.get("expected_plan"), dict):
        raise ValueError(f"{reference_path} must contain expected_plan object")


def _reference_paths(curriculum_dir: Path) -> list[Path]:
    paths = sorted(curriculum_dir.glob("*/teacher_reference.json"))
    if not paths:
        raise FileNotFoundError(f"no Implementer teacher references found in {curriculum_dir}")
    return paths


def _resolve_project_dir(root: Path, reference_path: Path, reference: dict[str, Any]) -> Path:
    project = Path(str(reference.get("project_dir") or reference_path.parent / "source"))
    if not project.is_absolute():
        project = root / project
    if not project.is_dir():
        raise FileNotFoundError(f"curriculum project not found: {project}")
    return project.resolve()


def _sources(rows: Any, *, key: str) -> list[str]:
    if not isinstance(rows, list):
        return []
    return sorted(str(row.get(key)) for row in rows if isinstance(row, dict) and row.get(key))


def _strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return sorted(str(item) for item in value if item is not None)
    if value is None:
        return []
    return [str(value)]


def _expected_covered(expected: Any, actual: Any) -> bool:
    expected_values = _strings(expected)
    actual_text = "\n".join(_strings(actual)).lower()
    return all(item.lower() in actual_text for item in expected_values)


def _ratio(numerator: float, denominator: float) -> float:
    return 1.0 if denominator == 0 else round(numerator / denominator, 4)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
