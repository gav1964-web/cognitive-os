"""Sandbox execution and evidence-backed reassessment for project development."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .generated_stub_admission import inspect_generated_function_stubs
from .programmer_executor import run_programmer_executor
from .project_failure_evidence_packet import is_complete_failure_evidence_packet
from .project_recognition import recognize_project
from .role_pipeline_stages import artifact_by_type
from .role_project_analysis import analyze_role_project
from .project_development_experiment_feedback import (
    blocked_artifacts as _blocked_artifacts,
    build_project_development_execution_feedback,
    not_requested_artifacts as _not_requested_artifacts,
)
from .project_native_failure_process import _project_version_hint


IGNORED_DIGEST_PARTS = {".git", ".pytest_cache", "__pycache__", ".mypy_cache", ".ruff_cache"}


def run_project_development_experiment(
    *,
    root: Path,
    project_dir: Path,
    goal: str,
    decision: dict[str, Any],
    outcome_contract: dict[str, Any],
    handoff: dict[str, Any],
    artifacts: dict[str, dict[str, Any]],
    requested: bool,
    policy: dict[str, Any],
    recognition: dict[str, Any],
    use_l45_llm: bool = False,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if not requested:
        return _not_requested_artifacts()
    admission = _admission(handoff, artifacts, policy, recognition)
    if admission["status"] != "admitted":
        return _blocked_artifacts(admission)
    before = _project_digest(project_dir)
    result = run_programmer_executor(
        root=root,
        project_dir=project_dir,
        technical_spec=artifact_by_type(artifacts, "TechnicalSpec"),
        implementation_plan=artifact_by_type(artifacts, "ImplementationPlan"),
        test_plan=artifact_by_type(artifacts, "TestPlan"),
        task_tree=artifact_by_type(artifacts, "ProgrammerTaskTree"),
        run_verification=True,
        apply_source=False,
        max_commands=int(dict(policy["execution_policy"]).get("maximum_verification_commands") or 3),
        # Keep Windows virtualenv cache paths below MAX_PATH during native replay.
        execution_base_dir=root / ".pde",
        use_l45_llm=use_l45_llm,
    )
    after = _project_digest(project_dir)
    patch = _read_artifact(result.get("patch_package_path"))
    test_result = _read_artifact(result.get("test_result_path"))
    issue = dict(decision.get("selected_issue") or {})
    nodeids = [
        str(nodeid)
        for evidence in issue.get("failure_evidence") or []
        if isinstance(evidence, dict)
        for nodeid in evidence.get("failing_nodeids") or []
        if nodeid
    ]
    sandbox = Path(str(result.get("execution_project") or dict(patch.get("patch_synthesis") or {}).get("sandbox_project") or ""))
    stub_admission = (
        inspect_generated_function_stubs(
            original_project=project_dir,
            sandbox_project=sandbox,
            patch=patch,
        )
        if patch.get("status") == "prepared" and sandbox.is_dir()
        else {
            "artifact_type": "GeneratedFunctionStubAdmission",
            "status": "not_requested",
            "violations": [],
            "parse_failures": [],
        }
    )
    from .project_native_failure_intake import run_project_native_verification
    native_verification = (
        run_project_native_verification(
            root=root, project=sandbox, failing_nodeids=nodeids, policy=policy,
            project_version_hint=_project_version_hint(project_dir),
        )
        if patch.get("status") == "prepared" and sandbox.is_dir() and nodeids and stub_admission.get("status") == "passed"
        else {
            "artifact_type": "ProjectNativeVerificationResult",
            "status": "not_requested",
            "failing_nodeids": nodeids,
            "reason": "generated_function_stub_blocked" if stub_admission.get("status") == "blocked" else None,
        }
    )
    experiment = _experiment_artifact(
        result, patch, test_result, native_verification, stub_admission, admission, before, after, decision, policy
    )
    reassessment = _reassess(
        root=root,
        goal=goal,
        decision=decision,
        outcome_contract=outcome_contract,
        experiment=experiment,
        test_result=test_result,
        policy=policy,
        recognition=recognition,
    )
    return experiment, reassessment, _validated_memory(decision, experiment, reassessment, policy)


def _admission(
    handoff: dict[str, Any],
    artifacts: dict[str, dict[str, Any]],
    policy: dict[str, Any],
    recognition: dict[str, Any],
) -> dict[str, Any]:
    execution = dict(policy["execution_policy"])
    technical_spec = _artifact_or_empty(artifacts, "TechnicalSpec")
    implementation_plan = _artifact_or_empty(artifacts, "ImplementationPlan")
    extraction_contract = dict(technical_spec.get("extraction_contract") or {})
    implementation_delta = dict(implementation_plan.get("implementation_delta") or {})
    intent = dict(implementation_delta.get("intent") or {})
    packet = dict(intent.get("failure_evidence_packet") or {})
    bounded_training_replay = _bounded_training_replay(
        intent=intent,
        packet=packet,
        allowed_operator_ids=list(extraction_contract.get("allowed_operator_ids") or []),
    )
    checks = {
        "role_handoff_aligned": handoff.get("status") == execution.get("required_handoff_status"),
        "review_allows_sandbox": handoff.get("review_recommendation") in set(execution.get("allowed_review_recommendations") or []),
        "required_artifacts_present": all(
            _artifact_or_empty(artifacts, kind).get("artifact_type") == kind
            for kind in ("TechnicalSpec", "ImplementationPlan", "TestPlan", "ProgrammerTaskTree")
        ),
        "implementation_delta_ready": implementation_delta.get("status") == "ready",
        "source_apply_disabled": execution.get("apply_source") is False,
        "recognition_pilot_route_allows_experiment": (
            dict(recognition.get("pilot_route") or {}).get("status")
            == "eligible_for_full_chain"
        ) or bounded_training_replay,
    }
    return {
        "artifact_type": "ProjectDevelopmentExperimentAdmission",
        "status": "admitted" if all(checks.values()) else "blocked",
        "checks": checks,
        "blocking_reasons": [name for name, passed in checks.items() if not passed],
        "contract_mode": technical_spec.get("contract_mode"),
        "allowed_operator_ids": list(extraction_contract.get("allowed_operator_ids") or []),
        "implementation_delta_status": implementation_delta.get("status"),
        "bounded_training_replay_override": bounded_training_replay,
    }


def _bounded_training_replay(
    *, intent: dict[str, Any], packet: dict[str, Any],
    allowed_operator_ids: list[Any],
) -> bool:
    authority = str(intent.get("authority") or "")
    if authority not in {"explicit_training_replay", "explicit_llm_training_replay"}:
        return False
    if not is_complete_failure_evidence_packet(
        packet, target=str(intent.get("target_symbol") or "")
    ):
        return False
    operator_id = str(intent.get("operator_id") or "")
    intent_operators = [str(value) for value in intent.get("allowed_operator_ids") or []]
    contract_operators = [str(value) for value in allowed_operator_ids]
    if authority == "explicit_training_replay":
        return bool(operator_id) and intent_operators == [operator_id] == contract_operators
    return not operator_id and not intent_operators and not contract_operators


def _artifact_or_empty(artifacts: dict[str, dict[str, Any]], artifact_type: str) -> dict[str, Any]:
    return next(
        (artifact for artifact in artifacts.values() if artifact.get("artifact_type") == artifact_type),
        {},
    )


def _experiment_artifact(
    result: dict[str, Any],
    patch: dict[str, Any],
    test_result: dict[str, Any],
    native_verification: dict[str, Any],
    stub_admission: dict[str, Any],
    admission: dict[str, Any],
    before: str,
    after: str,
    decision: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    issue = dict(decision.get("selected_issue") or {})
    patch_synthesis = dict(patch.get("patch_synthesis") or {})
    scope_ok = _patch_scope_aligned(
        patch, list(issue.get("affected_targets") or []) or list(issue.get("evidence") or [])
    )
    source_unchanged = before == after and result.get("source_code_changes") is False
    native_authority = native_verification.get("status") == "passed"
    checks = {
        "executor_completed": result.get("status") == "ok" or native_authority,
        "patch_package_prepared": patch.get("artifact_type") == "PatchPackage" and patch.get("status") == "prepared",
        "targeted_acceptance_passed": (
            dict(native_verification.get("targeted_replay") or {}).get("status") == "passed"
            if native_verification.get("status") != "not_requested"
            else dict(test_result.get("executable_acceptance_result") or {}).get("status") == "passed"
        ),
        "verification_passed": (
            dict(native_verification.get("regression_suite") or {}).get("status") == "passed"
            if native_verification.get("status") != "not_requested"
            else test_result.get("status") == "ok"
        ),
        "original_source_digest_unchanged": source_unchanged,
        "patch_scope_within_issue_evidence": scope_ok,
        "no_generated_function_stubs": stub_admission.get("status") == "passed",
    }
    required = dict(policy["execution_policy"])
    if not required.get("require_original_source_digest_unchanged", True):
        checks["original_source_digest_unchanged"] = True
    if not required.get("require_patch_scope_within_issue_evidence", True):
        checks["patch_scope_within_issue_evidence"] = True
    return {
        "artifact_type": "ProjectDevelopmentExperiment",
        "status": "verified" if all(checks.values()) else "failed",
        "admission": admission,
        "issue_id": issue.get("issue_id"),
        "selected_target": dict(result.get("reviewer_handoff") or {}).get("target") or dict(patch.get("implementation_target") or {}).get("candidate"),
        "sandbox_project": result.get("execution_project") or dict(patch.get("patch_synthesis") or {}).get("sandbox_project"),
        "execution_dir": result.get("execution_dir"),
        "patch_package_path": result.get("patch_package_path"),
        "test_result_path": result.get("test_result_path"),
        "patch_count": len(list(patch.get("patches") or [])),
        "patch_kinds": [str(row.get("kind") or "") for row in patch.get("patches") or [] if isinstance(row, dict)],
        "patch_synthesis_status": patch_synthesis.get("status"),
        "patch_reason": patch_synthesis.get("reason") or patch.get("reason"),
        "reducer_selection": dict(patch_synthesis.get("reducer_selection") or {}),
        "project_native_verification": native_verification,
        "generated_function_stub_admission": stub_admission,
        "checks": checks,
        "source_invariant": {"before": before, "after": after, "unchanged": source_unchanged},
        "apply_source": False,
    }


def _reassess(
    *, root: Path, goal: str, decision: dict[str, Any], outcome_contract: dict[str, Any],
    experiment: dict[str, Any], test_result: dict[str, Any], policy: dict[str, Any],
    recognition: dict[str, Any],
) -> dict[str, Any]:
    sandbox = Path(str(experiment.get("sandbox_project") or ""))
    if experiment.get("status") != "verified" or not sandbox.is_dir():
        return _reassessment("not_validated", decision, outcome_contract, {}, experiment, test_result)
    report = analyze_role_project(root=root, project_dir=sandbox, goal=goal)["project_map_report"]
    recognition = recognize_project(
        project=sandbox.name,
        project_report=report,
        classification=dict(recognition.get("classification") or {}) or None,
    )
    from .project_development import build_development_diagnosis
    diagnosis = build_development_diagnosis(
        project=sandbox.name, project_report=report, recognition=recognition, policy=policy,
    )
    selected_issue = dict(decision.get("selected_issue") or {})
    reducers = (
        list(selected_issue.get("allowed_operator_ids") or [])
        if selected_issue.get("failure_specific_reducer_required") is True
        else list(dict(policy.get("verified_issue_reducers") or {}).get(str(selected_issue.get("rule_id") or "")) or [])
    )
    return _reassessment(
        "evaluated", decision, outcome_contract, diagnosis, experiment, test_result,
        verified_patch_reducers=reducers,
    )


def _reassessment(
    phase: str, decision: dict[str, Any], outcome_contract: dict[str, Any], diagnosis: dict[str, Any],
    experiment: dict[str, Any], test_result: dict[str, Any], *, verified_patch_reducers: list[str] | None = None,
) -> dict[str, Any]:
    issue = dict(decision.get("selected_issue") or {})
    same = next((dict(row) for row in diagnosis.get("issues", []) if row.get("rule_id") == issue.get("rule_id")), {})
    baseline = set(str(value) for value in outcome_contract.get("baseline_evidence") or [])
    current = set(str(value) for value in same.get("evidence") or [])
    matched_reducers = sorted(set(experiment.get("patch_kinds") or []) & set(verified_patch_reducers or []))
    reduced = phase == "evaluated" and (not same or len(current) < len(baseline) or bool(matched_reducers))
    summary = dict(test_result.get("summary") or {})
    native = dict(experiment.get("project_native_verification") or {})
    native_targeted = dict(native.get("targeted_replay") or {}).get("status") == "passed"
    native_regression = dict(native.get("regression_suite") or {}).get("status") == "passed"
    checks = {
        "issue_evidence_reproduced_before_change": bool(baseline),
        "selected_issue_resolved_or_reduced": reduced,
        "targeted_acceptance_passed": native_targeted or dict(test_result.get("executable_acceptance_result") or {}).get("status") == "passed",
        "regression_suite_passed": native_regression or (test_result.get("status") == "ok" and int(summary.get("failed") or 0) == 0),
        "source_scope_preserved": bool(dict(experiment.get("source_invariant") or {}).get("unchanged")) and bool(dict(experiment.get("checks") or {}).get("patch_scope_within_issue_evidence")),
    }
    return {
        "artifact_type": "ProjectDevelopmentReassessment",
        "status": "validated" if all(checks.values()) else "not_validated",
        "issue_id": issue.get("issue_id"),
        "baseline_rule_id": issue.get("rule_id"),
        "baseline_evidence_count": len(baseline),
        "remaining_evidence_count": len(current) if phase == "evaluated" else None,
        "verification_scope": "project_native_failure_replay_and_regression" if native else "executor_allowlist_and_generated_acceptance",
        "issue_disposition": "resolved" if reduced and not same else "reduced" if reduced else "unchanged_or_inconclusive",
        "verified_issue_reducers": matched_reducers,
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "diagnosis": diagnosis,
    }


def _validated_memory(
    decision: dict[str, Any], experiment: dict[str, Any], reassessment: dict[str, Any], policy: dict[str, Any]
) -> dict[str, Any]:
    required = dict(policy["memory_policy"]).get("required_reassessment_status")
    validated = experiment.get("status") == "verified" and reassessment.get("status") == required
    return {
        "artifact_type": "ProjectDevelopmentValidatedMemory",
        "status": "validated" if validated else "not_promoted",
        "issue": dict(decision.get("selected_issue") or {}),
        "option": dict(decision.get("selected_option") or {}),
        "experiment_status": experiment.get("status"),
        "reassessment_status": reassessment.get("status"),
        "evidence_paths": [experiment.get("patch_package_path"), experiment.get("test_result_path")],
        "authority": "verified_sandbox_outcome" if validated else "none",
        "model_claim_is_evidence": False,
    }


def _patch_scope_aligned(patch: dict[str, Any], evidence: list[str]) -> bool:
    allowed = {str(value).split(":", 1)[0].replace("\\", "/").lower() for value in evidence if ".py:" in str(value)}
    changed = {
        str(row.get("file") or row.get("path") or "").replace("\\", "/").lower()
        for row in patch.get("patches") or [] if isinstance(row, dict)
    }
    return bool(allowed) and bool(changed) and changed <= allowed


def _project_digest(project: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in project.rglob("*") if item.is_file() and not (set(item.parts) & IGNORED_DIGEST_PARTS)):
        digest.update(path.relative_to(project).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _read_artifact(value: Any) -> dict[str, Any]:
    path = Path(str(value or ""))
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
