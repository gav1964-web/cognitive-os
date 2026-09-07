"""Ground-truth semantic evaluation for the certified narrow project lane."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .foundation_semantic_quality import evaluate_foundation_semantic_quality
from .framework_plugin_role_semantics import artifact_digest


REQUIRED_ROLES = (
    "project_analyzer", "architect", "spec_writer",
    "implementer", "tester", "reviewer",
)
REQUIRED_STRATA = ("cli_local_tool", "library_pure_transform")


def evaluate_narrow_type_role_semantics(
    *, cases: list[dict[str, Any]], target_score: float = 9.7,
    evaluation_split: str = "calibration",
) -> dict[str, Any]:
    evaluated = [_evaluate_case(dict(case), target_score=target_score) for case in cases]
    stratum_checks = {
        stratum: _stratum_check(evaluated, stratum) for stratum in REQUIRED_STRATA
    }
    all_cases_pass = bool(evaluated) and all(row["status"] == "passed" for row in evaluated)
    checks = {
        "all_cases_semantically_passed": all_cases_pass,
        "required_strata_covered": all(row["case_count"] >= 2 for row in stratum_checks.values()),
        "independent_lineages_per_stratum": all(
            row["source_lineage_count"] >= 2 for row in stratum_checks.values()
        ),
        "holdout_independent_owners_per_stratum": evaluation_split != "holdout" or all(
            row["source_owner_count"] >= 2 for row in stratum_checks.values()
        ),
        "all_roles_at_target": all(
            score is not None and score >= target_score
            for score in _worst_role_scores(evaluated).values()
        ),
        "all_role_artifacts_auditable": bool(evaluated)
        and all(row["role_artifacts_auditable"] for row in evaluated),
        "all_project_changes_evaluated": bool(evaluated)
        and all(row["development_change_evaluated"] for row in evaluated),
    }
    body = {
        "artifact_type": "NarrowTypeRoleSemanticEvidence",
        "schema_version": "narrow_type_role_semantic_evidence.v1",
        "status": "passed" if all(checks.values()) else "evidence_required",
        "evaluation_split": evaluation_split,
        "target_score": target_score,
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "role_scores": _worst_role_scores(evaluated),
        "strata": stratum_checks,
        "cases": evaluated,
        "source_apply": False,
        "promotion_applied": False,
    }
    return {**body, "evidence_digest": _digest(body)}


def _evaluate_case(case: dict[str, Any], *, target_score: float) -> dict[str, Any]:
    role_run = dict(case.get("role_run") or {})
    execution_run = dict(case.get("execution_run") or {})
    artifacts = dict(role_run.get("role_artifacts") or {})
    project_map = dict(artifacts.get("project_map_report") or {})
    adr = dict(artifacts.get("architecture_decision") or {})
    spec = dict(artifacts.get("technical_spec") or {})
    recognition = dict(role_run.get("recognition") or {})
    classification = dict(recognition.get("classification") or {})
    decision = dict(role_run.get("decision") or {})
    issue = dict(decision.get("selected_issue") or {})
    handoff = dict(role_run.get("role_chain_handoff") or {})
    experiment = dict(execution_run.get("experiment") or {})
    native = dict(experiment.get("project_native_verification") or {})
    target = str(handoff.get("selected_target") or "")
    expected = str(case.get("project_stratum") or "")
    foundation = evaluate_foundation_semantic_quality({"artifacts": artifacts})
    artifact_audit = _artifact_audit(artifacts)
    checks = {
        "project_analyzer": {
            "project_identity_matches_expected_stratum": classification.get("effective_project_identity") == expected,
            "project_archetype_matches_ground_truth": not case.get("expected_project_archetype")
            or classification.get("project_archetype") == case.get("expected_project_archetype"),
            "recognition_is_source_backed": recognition.get("status") == "recognized"
            and bool(dict(recognition.get("evidence") or {}).get("project_analyzer_evidence")),
            "project_map_is_source_backed": bool(project_map.get("summary"))
            and bool(project_map.get("answers"))
            and bool(project_map.get("source_health")),
            "development_issue_is_source_backed": bool(issue.get("evidence"))
            and bool(issue.get("affected_targets")),
            "development_issue_has_single_bounded_target": len(issue.get("affected_targets") or []) == 1,
            "foundation_quality_passed": _foundation_score(foundation, "project_analyzer") >= target_score,
        },
        "architect": {
            "architecture_artifact_is_valid": adr.get("status") == "ok",
            "role_handoff_is_aligned": handoff.get("status") == "completed_aligned"
            and handoff.get("issue_target_aligned") is True,
            "selected_target_is_issue_bound": _target_matches_issue(target, issue),
            "first_slice_contains_selected_target": target in _first_slice_targets(adr),
            "foundation_quality_passed": _foundation_score(foundation, "architect") >= target_score,
        },
        "spec_writer": {
            "technical_spec_is_valid": spec.get("status") == "ok",
            "spec_target_matches_handoff": _spec_target(spec) == target and bool(target),
            "requirements_are_present": bool(spec.get("requirements")),
            "requirements_are_target_bound": _requirements_target_bound(spec, target),
            "acceptance_is_bounded": 0 < len(spec.get("acceptance_criteria") or []) <= 20,
            "acceptance_traceability_is_exact": _acceptance_traceability_exact(spec, target),
            "verification_is_target_bound": _verification_target_bound(spec, target),
            "foundation_quality_passed": _foundation_score(foundation, "spec_writer") >= target_score,
        },
        "implementer": {
            "validated_run_matches_project": execution_run.get("project") == role_run.get("project"),
            "validated_run_matches_target": str(dict(execution_run.get("role_chain_handoff") or {}).get("selected_target") or "") == target,
            "patch_was_prepared": int(experiment.get("patch_count") or 0) > 0
            and experiment.get("patch_synthesis_status") == "prepared",
            "executor_completed": dict(experiment.get("checks") or {}).get("executor_completed") is True,
            "no_generated_function_stubs": dict(experiment.get("checks") or {}).get("no_generated_function_stubs") is True,
        },
        "tester": {
            "experiment_is_verified": experiment.get("status") == "verified",
            "native_verification_passed": native.get("status") == "passed",
            "targeted_replay_passed": dict(native.get("targeted_replay") or {}).get("status") == "passed",
            "regression_suite_passed": dict(native.get("regression_suite") or {}).get("status") == "passed",
            "verification_check_passed": dict(experiment.get("checks") or {}).get("verification_passed") is True,
        },
        "reviewer": {
            "project_run_was_validated": execution_run.get("status") == "experiment_validated",
            "all_experiment_checks_passed": bool(experiment.get("checks"))
            and all(dict(experiment.get("checks") or {}).values()),
            "source_digest_unchanged": dict(experiment.get("source_invariant") or {}).get("unchanged") is True,
            "source_apply_disabled": experiment.get("apply_source") is False,
            "stub_admission_passed": dict(experiment.get("generated_function_stub_admission") or {}).get("status") == "passed",
        },
    }
    role_scores = {
        role: _binary_score(role_checks) for role, role_checks in checks.items()
    }
    artifact_digests = {
        name: artifact_digest(value) for name, value in artifacts.items()
        if name in {"project_map_report", "architecture_decision", "technical_spec"}
        and isinstance(value, dict)
    }
    development_evaluated = all(
        all(checks[role].values()) for role in ("implementer", "tester", "reviewer")
    )
    status = "passed" if artifact_audit and development_evaluated and min(role_scores.values()) >= target_score else "evidence_required"
    return {
        "project": role_run.get("project"),
        "project_stratum": expected,
        "source_lineage": case.get("source_lineage"),
        "source_owner": case.get("source_owner"),
        "status": status,
        "role_scores": role_scores,
        "checks": checks,
        "failed_checks": {
            role: [name for name, passed in rows.items() if not passed]
            for role, rows in checks.items() if not all(rows.values())
        },
        "role_artifacts": artifacts,
        "role_artifact_digests": artifact_digests,
        "role_artifacts_auditable": artifact_audit,
        "development_change_evaluated": development_evaluated,
        "role_run_digest": _digest(role_run),
        "execution_run_digest": _digest(execution_run),
    }


def _artifact_audit(artifacts: dict[str, Any]) -> bool:
    return all(
        isinstance(artifacts.get(name), dict) and bool(artifacts[name])
        for name in ("project_map_report", "architecture_decision", "technical_spec")
    )


def _target_matches_issue(target: str, issue: dict[str, Any]) -> bool:
    targets = [str(value) for value in issue.get("affected_targets") or []]
    if target in targets:
        return True
    path = target.split(":", 1)[0].replace("\\", "/").lower()
    return bool(path) and any(
        str(value).split(":", 1)[0].replace("\\", "/").lower() == path
        for value in targets
    )


def _first_slice_targets(adr: dict[str, Any]) -> list[str]:
    return [str(value) for value in dict(adr.get("first_slice_contract") or {}).get("targets") or []]


def _spec_target(spec: dict[str, Any]) -> str:
    return str(dict(spec.get("extraction_contract") or {}).get("candidate") or "")


def _requirements_target_bound(spec: dict[str, Any], target: str) -> bool:
    rows = [row for row in spec.get("requirements") or [] if isinstance(row, dict)]
    return 3 <= len(rows) <= 10 and all(str(row.get("target") or "") == target for row in rows)


def _acceptance_traceability_exact(spec: dict[str, Any], target: str) -> bool:
    acceptance = [row for row in spec.get("acceptance_criteria") or [] if isinstance(row, dict)]
    traceability = [row for row in spec.get("traceability_table") or [] if isinstance(row, dict)]
    acceptance_ids = {str(row.get("id") or "") for row in acceptance}
    traced_ids = {str(row.get("acceptance_id") or "") for row in traceability}
    requirement_ids = {
        str(row.get("id") or "") for row in spec.get("requirements") or []
        if isinstance(row, dict)
    }
    return (
        bool(acceptance_ids)
        and acceptance_ids == traced_ids
        and all(str(row.get("target") or "") == target for row in traceability)
        and all(str(row.get("requirement_id") or "") in requirement_ids for row in traceability)
    )


def _verification_target_bound(spec: dict[str, Any], target: str) -> bool:
    strategy = dict(spec.get("verification_strategy") or {})
    rows = [
        row for group in strategy.values() if isinstance(group, list)
        for row in group if isinstance(row, dict)
    ]
    return bool(rows) and all(str(row.get("target") or "") == target for row in rows)


def _foundation_score(report: dict[str, Any], role: str) -> float:
    return float(dict(report.get("role_scores") or {}).get(role) or 0.0)


def _binary_score(checks: dict[str, bool]) -> float:
    return round(10.0 * sum(bool(value) for value in checks.values()) / max(1, len(checks)), 2)


def _stratum_check(cases: list[dict[str, Any]], stratum: str) -> dict[str, Any]:
    selected = [row for row in cases if row.get("project_stratum") == stratum]
    return {
        "case_count": len(selected),
        "source_lineage_count": len({row.get("source_lineage") for row in selected if row.get("source_lineage")}),
        "source_owner_count": len({row.get("source_owner") for row in selected if row.get("source_owner")}),
        "projects": sorted(str(row.get("project")) for row in selected),
        "status": "passed" if len(selected) >= 2 and all(row.get("status") == "passed" for row in selected) else "evidence_required",
    }


def _worst_role_scores(cases: list[dict[str, Any]]) -> dict[str, float | None]:
    return {
        role: min(
            (float(dict(row.get("role_scores") or {})[role]) for row in cases if role in dict(row.get("role_scores") or {})),
            default=None,
        )
        for role in REQUIRED_ROLES
    }


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
