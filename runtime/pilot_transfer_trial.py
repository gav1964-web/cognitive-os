"""Bind a frozen blind corpus and executable full-chain evidence to pilot admission."""

from __future__ import annotations

from typing import Any

from .pilot_profile import evaluate_pilot_candidate, load_pilot_profile


def evaluate_pilot_transfer_trial(
    *,
    selection: dict[str, Any],
    full_chain_report: dict[str, Any],
    role_readiness: dict[str, Any],
    reviewer_adversarial: dict[str, Any],
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = profile or load_pilot_profile()
    selected = {str(row.get("full_name")): dict(row) for row in selection.get("projects", [])}
    cases = list(full_chain_report.get("cases") or [])
    case_by_project = {str(row.get("project")): dict(row) for row in cases}
    evidence_rows = []
    for full_name, source in selected.items():
        project_key = full_name.replace("/", "__")
        case = case_by_project.get(project_key, {})
        executor = dict(case.get("executor") or {})
        classification = dict(case.get("project_classification") or {})
        checks = {
            "case_present": bool(case),
            "full_chain_ok": case.get("status") == "ok",
            "quality_gate_passed": float(case.get("quality_score") or 0.0) >= 0.92,
            "handoff_loss_zero": not case.get("failed_checks"),
            "executor_callable": executor.get("acceptance_signal") == "executable_callable"
            and int(executor.get("callable_harness_count") or 0) > 0,
            "executable_acceptance_passed": executor.get("executable_acceptance") == "passed",
            "source_unchanged": case.get("source_code_changes") is False,
        }
        evidence_rows.append({
            "full_name": full_name,
            "owner": full_name.split("/", 1)[0].lower(),
            "selection_stratum": source.get("stratum"),
            "project_stratum": classification.get("project_stratum"),
            "risk_profiles": list(classification.get("risk_profiles") or []),
            "effect_mode": case.get("effect_mode"),
            "status": "passed" if all(checks.values()) else "failed",
            "checks": checks,
        })
    passed = [row for row in evidence_rows if row["status"] == "passed"]
    lineages = {row["owner"] for row in passed}
    handoff_loss = sum(not row["checks"]["handoff_loss_zero"] for row in evidence_rows)
    transfer = {
        "blind_projects": len(passed),
        "independent_lineages": len(lineages),
        "handoff_loss": handoff_loss,
    }
    admissions = [
        evaluate_pilot_candidate(
            project_stratum=str(row.get("project_stratum") or "unknown_new_archetype"),
            risk_profiles=list(row.get("risk_profiles") or []),
            effect_mode=str(row.get("effect_mode") or "sandbox_only"),
            requested_mode="sandbox_patch",
            role_readiness=role_readiness,
            transfer_evidence=transfer,
            reviewer_adversarial=reviewer_adversarial,
            profile=policy,
        )
        for row in evidence_rows
    ]
    checks = {
        "selection_frozen": selection.get("selection_frozen") is True,
        "minimum_projects_selected": len(selected) >= 2,
        "unique_selected_owners": len({name.split("/", 1)[0].lower() for name in selected}) >= 2,
        "all_selected_projects_measured": len(evidence_rows) == len(selected) and all(row["checks"]["case_present"] for row in evidence_rows),
        "all_transfer_cases_passed": len(passed) == len(selected),
        "all_candidate_admissions_eligible": bool(admissions) and all(row.get("status") == "eligible" for row in admissions),
    }
    return {
        "artifact_type": "PilotTransferTrialReport",
        "schema_version": "pilot_transfer_trial.v1",
        "status": "eligible" if all(checks.values()) else "blocked",
        "profile_id": policy.get("profile_id"),
        "checks": checks,
        "transfer_evidence": transfer,
        "cases": evidence_rows,
        "candidate_admissions": admissions,
        "blocking_reasons": [name for name, passed_check in checks.items() if not passed_check],
        "safety": {"source_apply_allowed": False, "source_code_changes": 0, "registry_changes": 0},
    }
