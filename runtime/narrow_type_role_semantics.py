"""Ground-truth semantic evaluation for the certified narrow project lane."""

from __future__ import annotations

from typing import Any

from .foundation_semantic_quality import evaluate_foundation_semantic_quality
from .foundation_semantic_quality_policy import load_foundation_semantic_quality_policy
from .framework_plugin_role_semantics import artifact_digest
from .narrow_type_role_evidence import digest_evidence, stratum_check, worst_role_scores


REQUIRED_ROLES = (
    "project_analyzer", "architect", "spec_writer",
    "implementer", "tester", "reviewer",
)
REQUIRED_STRATA = ("cli_local_tool", "library_pure_transform")


def evaluate_narrow_type_role_semantics(
    *, cases: list[dict[str, Any]], target_score: float = 9.7,
    evaluation_split: str = "calibration",
) -> dict[str, Any]:
    policy = load_foundation_semantic_quality_policy()
    evaluated = [
        _evaluate_case(
            dict(case), target_score=target_score, policy=policy,
            evaluation_split=evaluation_split,
        )
        for case in cases
    ]
    stratum_checks = {
        stratum: stratum_check(evaluated, stratum) for stratum in REQUIRED_STRATA
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
            for score in worst_role_scores(evaluated, REQUIRED_ROLES).values()
        ),
        "all_role_artifacts_auditable": bool(evaluated)
        and all(row["role_artifacts_auditable"] for row in evaluated),
        "all_project_changes_evaluated": bool(evaluated)
        and all(row["development_change_evaluated"] for row in evaluated),
    }
    body = {
        "artifact_type": "NarrowTypeRoleSemanticEvidence",
        "schema_version": "narrow_type_role_semantic_evidence.v2",
        "status": "passed" if all(checks.values()) else "evidence_required",
        "evaluation_split": evaluation_split,
        "target_score": target_score,
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "role_scores": worst_role_scores(evaluated, REQUIRED_ROLES),
        "strata": stratum_checks,
        "cases": evaluated,
        "source_apply": False,
        "promotion_applied": False,
    }
    return {**body, "evidence_digest": digest_evidence(body)}


def _evaluate_case(
    case: dict[str, Any], *, target_score: float, policy: dict[str, Any],
    evaluation_split: str,
) -> dict[str, Any]:
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
    foundation = evaluate_foundation_semantic_quality({"artifacts": artifacts}, policy=policy)
    artifact_audit = _artifact_audit(artifacts)
    causal_diagnosis = _causal_diagnosis_present(issue)
    concrete_design = _concrete_repair_design(adr, target)
    implementation_ready = _implementation_ready(spec, target)
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
            "development_issue_has_bounded_target_scope": _bounded_target_scope(issue),
            "failure_behavior_is_characterized": _failure_behavior_characterized(issue),
            "causal_diagnosis_is_present": causal_diagnosis,
            "foundation_quality_passed": _foundation_score(foundation, "project_analyzer") >= target_score,
        },
        "architect": {
            "architecture_artifact_is_valid": adr.get("status") == "ok",
            "role_handoff_is_aligned": handoff.get("status") == "completed_aligned"
            and handoff.get("issue_target_aligned") is True,
            "selected_target_is_issue_bound": _target_matches_issue(target, issue),
            "first_slice_contains_selected_target": target in _first_slice_targets(adr),
            "causal_diagnosis_is_consumed": causal_diagnosis,
            "repair_design_is_concrete": concrete_design,
            "implementation_path_is_ready": implementation_ready,
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
            "repair_action_is_concrete": _concrete_spec_action(spec, target),
            "implementation_delta_is_ready": implementation_ready,
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
    structural_scores = {
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
    role_scores, applied_caps = _validated_role_scores(
        structural_scores,
        policy=policy,
        causal_diagnosis=causal_diagnosis,
        concrete_design=concrete_design,
        implementation_ready=implementation_ready,
        development_evaluated=development_evaluated,
        evaluation_split=evaluation_split,
        regression_scope_kind=str(case.get("regression_scope_kind") or "full"),
    )
    status = "passed" if artifact_audit and development_evaluated and min(role_scores.values()) >= target_score else "evidence_required"
    return {
        "project": role_run.get("project"),
        "project_stratum": expected,
        "source_lineage": case.get("source_lineage"),
        "source_owner": case.get("source_owner"),
        "status": status,
        "role_scores": role_scores,
        "structural_role_scores": structural_scores,
        "score_caps_applied": applied_caps,
        "checks": checks,
        "failed_checks": {
            role: [name for name, passed in rows.items() if not passed]
            for role, rows in checks.items() if not all(rows.values())
        },
        "role_artifacts": artifacts,
        "role_artifact_digests": artifact_digests,
        "role_artifacts_auditable": artifact_audit,
        "development_change_evaluated": development_evaluated,
        "role_run_digest": digest_evidence(role_run),
        "execution_run_digest": digest_evidence(execution_run),
    }


def _artifact_audit(artifacts: dict[str, Any]) -> bool:
    return all(
        isinstance(artifacts.get(name), dict) and bool(artifacts[name])
        for name in ("project_map_report", "architecture_decision", "technical_spec")
    )


def _failure_behavior_characterized(issue: dict[str, Any]) -> bool:
    rows = [row for row in issue.get("failure_evidence") or [] if isinstance(row, dict)]
    return bool(rows) and all(
        row.get("detail") and row.get("failure_signature") and row.get("failing_nodeids")
        for row in rows
    )


def _bounded_target_scope(issue: dict[str, Any]) -> bool:
    targets = [str(value) for value in issue.get("affected_targets") or [] if value]
    files = {value.split(":", 1)[0].replace("\\", "/").lower() for value in targets}
    return 1 <= len(targets) <= 3 and len(files) == 1


def _causal_diagnosis_present(issue: dict[str, Any]) -> bool:
    for key in ("causal_hypothesis", "root_cause", "failure_mechanism", "repair_hypothesis"):
        value = issue.get(key)
        if isinstance(value, dict) and _specific_text(value.get("mechanism") or value.get("statement")):
            return bool(value.get("evidence"))
        if _specific_text(value):
            return True
    return False


def _concrete_repair_design(adr: dict[str, Any], target: str) -> bool:
    synthesis = dict(adr.get("architecture_synthesis") or {})
    design = dict(adr.get("repair_design") or synthesis.get("repair_design") or {})
    return (
        str(design.get("target") or "") == target
        and _specific_text(design.get("mechanism"))
        and bool(design.get("evidence"))
    )


def _implementation_ready(spec: dict[str, Any], target: str) -> bool:
    delta = dict(spec.get("implementation_delta") or {})
    intent = dict(delta.get("intent") or {})
    return (
        delta.get("status") == "ready"
        and str(intent.get("target_symbol") or target) == target
        and bool(intent.get("operator_id") or intent.get("recipe") or intent.get("mutation"))
    )


def _concrete_spec_action(spec: dict[str, Any], target: str) -> bool:
    delta = dict(spec.get("implementation_delta") or {})
    intent = dict(delta.get("intent") or {})
    mutation = intent.get("mutation")
    mutation_text = (
        " ".join(str(value) for value in mutation.values())
        if isinstance(mutation, dict) else str(mutation or "")
    )
    has_bounded_action = bool(intent.get("operator_id")) or (
        intent.get("authority") == "explicit_llm_training_replay"
        and _specific_text(mutation_text)
    )
    if str(intent.get("target_symbol") or "") != target or not has_bounded_action:
        return False
    statements = " ".join(
        str(row.get("statement") or "")
        for row in spec.get("requirements") or [] if isinstance(row, dict)
    ).lower()
    return "approved failure reducer" not in statements


def _specific_text(value: Any) -> bool:
    return isinstance(value, str) and len(value.strip()) >= 24


def _validated_role_scores(
    structural: dict[str, float], *, policy: dict[str, Any],
    causal_diagnosis: bool, concrete_design: bool,
    implementation_ready: bool, development_evaluated: bool,
    evaluation_split: str, regression_scope_kind: str,
) -> tuple[dict[str, float], dict[str, list[dict[str, Any]]]]:
    scores = dict(structural)
    applied: dict[str, list[dict[str, Any]]] = {role: [] for role in REQUIRED_ROLES}
    caps = dict(policy.get("narrow_holdout_validation_caps") or {})

    def apply(reason: str) -> None:
        for role, value in dict(caps.get(reason) or {}).items():
            if role not in scores:
                continue
            cap = float(value)
            if scores[role] > cap:
                scores[role] = cap
                applied[role].append({"reason": reason, "cap": cap})

    if not causal_diagnosis:
        apply("missing_causal_diagnosis")
    if not concrete_design:
        apply("missing_concrete_repair_design")
    if not implementation_ready:
        apply("implementation_not_ready")
    if not development_evaluated:
        apply("change_not_validated")
    split_caps = dict(policy.get("narrow_evaluation_split_caps") or {})
    for reason in (
        evaluation_split,
        "scoped_regression" if regression_scope_kind != "full" else "",
    ):
        for role, value in dict(split_caps.get(reason) or {}).items():
            cap = float(value)
            if role in scores and scores[role] > cap:
                scores[role] = cap
                applied[role].append({"reason": reason, "cap": cap})
    return scores, {role: rows for role, rows in applied.items() if rows}


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
