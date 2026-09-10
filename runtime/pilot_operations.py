"""Supervised pilot run, review, and telemetry contracts."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Iterable

from .pilot_profile import evaluate_pilot_candidate, load_pilot_profile


HANDOFF_CHECKS = {
    "spec_target_is_advised_by_adr",
    "target_chain_preserved",
    "implementation_bound_to_spec",
    "tester_covers_contract",
    "review_conformance_passed",
}


def build_pilot_run_record(
    *,
    full_chain_report: dict[str, Any],
    transfer_report: dict[str, Any],
    role_readiness: dict[str, Any],
    reviewer_adversarial: dict[str, Any],
    profile: dict[str, Any] | None = None,
    requested_mode: str = "sandbox_patch",
) -> dict[str, Any]:
    policy = profile or load_pilot_profile()
    transfer = dict(transfer_report.get("transfer_evidence") or {})
    rows = []
    for raw in full_chain_report.get("cases") or []:
        case = dict(raw)
        classification = dict(case.get("project_classification") or {})
        admission = evaluate_pilot_candidate(
            project_stratum=str(classification.get("project_stratum") or "unknown_new_archetype"),
            risk_profiles=list(classification.get("risk_profiles") or []),
            effect_mode=str(case.get("effect_mode") or "sandbox_only"),
            requested_mode=requested_mode,
            role_readiness=role_readiness,
            transfer_evidence=transfer,
            reviewer_adversarial=reviewer_adversarial,
            profile=policy,
        )
        failed = [
            str(row.get("code")) for row in case.get("failed_checks") or []
            if isinstance(row, dict) and row.get("passed") is not True
        ]
        handoff_loss = [code for code in failed if code in HANDOFF_CHECKS]
        rows.append({
            "project": case.get("project"),
            "status": case.get("status"),
            "quality_score": float(case.get("quality_score") or 0.0),
            "project_stratum": classification.get("project_stratum"),
            "risk_profiles": list(classification.get("risk_profiles") or []),
            "project_recognition": dict(case.get("project_recognition") or {}),
            "effect_mode": case.get("effect_mode"),
            "admission": admission,
            "failed_checks": failed,
            "handoff_loss": handoff_loss,
            "first_pass": case.get("status") == "ok"
            and not failed
            and admission.get("status") == "eligible",
            "source_code_changes": bool(case.get("source_code_changes")),
        })
    safety_clean = all(not row["source_code_changes"] for row in rows)
    executable_ok = bool(rows) and all(
        row["status"] == "ok" and row["admission"]["status"] == "eligible" for row in rows
    )
    execution_status = "awaiting_human_review" if executable_ok and safety_clean else "controlled_stop"
    record = {
        "artifact_type": "PilotRunRecord",
        "schema_version": "pilot_run_record.v1",
        "run_id": _run_id(full_chain_report),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile_id": policy.get("profile_id"),
        "requested_mode": requested_mode,
        "status": execution_status,
        "execution_status": execution_status,
        "cases": rows,
        "summary": {
            "case_count": len(rows),
            "first_pass_count": sum(row["first_pass"] for row in rows),
            "handoff_loss_count": sum(len(row["handoff_loss"]) for row in rows),
            "controlled_stop_count": sum(row["status"] != "ok" for row in rows),
        },
        "human_review": {
            "required": True,
            "status": "pending",
            "allowed_decisions": ["approve", "rework", "stop"],
        },
        "safety": {
            "source_apply_allowed": False,
            "source_code_changes": sum(row["source_code_changes"] for row in rows),
            "registry_changes": 0,
        },
        "evidence": {
            "full_chain_report": full_chain_report.get("report_path"),
            "transfer_report": transfer_report.get("report_path"),
            "transfer_status": transfer_report.get("status"),
        },
    }
    record["evidence_digest"] = pilot_run_digest(record)
    return record


def review_pilot_run(
    record: dict[str, Any], *, decision: str, reviewer: str, note: str = ""
) -> dict[str, Any]:
    if decision not in {"approve", "rework", "stop"}:
        raise ValueError("pilot review decision must be approve, rework, or stop")
    if not reviewer.strip():
        raise ValueError("pilot review requires a reviewer identifier")
    expected = pilot_run_digest(record)
    if record.get("evidence_digest") != expected:
        raise ValueError("pilot run evidence digest mismatch")
    if decision == "approve" and record.get("execution_status", record.get("status")) != "awaiting_human_review":
        raise ValueError("only a clean awaiting_human_review run may be approved")
    reviewed = json.loads(json.dumps(record))
    reviewed["status"] = {
        "approve": "observed_approved",
        "rework": "observed_rework",
        "stop": "observed_stopped",
    }[decision]
    reviewed["human_review"] = {
        "required": True,
        "status": "completed",
        "decision": decision,
        "reviewer": reviewer.strip(),
        "note": note.strip(),
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "evidence_digest": expected,
    }
    return reviewed


def build_pilot_telemetry(
    records: Iterable[dict[str, Any]], *, profile: dict[str, Any] | None = None
) -> dict[str, Any]:
    policy = profile or load_pilot_profile()
    rows = [dict(row) for row in records]
    reviewed = [row for row in rows if dict(row.get("human_review") or {}).get("status") == "completed"]
    cases = [dict(case) for row in rows for case in row.get("cases") or []]
    case_rows = [
        (dict(case), row)
        for row in rows
        for case in row.get("cases") or []
        if isinstance(case, dict)
    ]
    handoff_codes = [str(code) for case in cases for code in case.get("handoff_loss") or []]
    gate = dict(policy.get("telemetry_gate") or {})
    reviewed_count = len(reviewed)
    first_pass = sum(
        case.get("first_pass") is True
        and dict(case.get("admission") or {}).get("status") == "eligible"
        for case in cases
    )
    eligible_cases = [
        case for case in cases
        if dict(case.get("admission") or {}).get("status") == "eligible"
    ]
    eligible_first_pass = sum(case.get("first_pass") is True for case in eligible_cases)
    blocked_cases = [
        (case, row) for case, row in case_rows
        if dict(case.get("admission") or {}).get("status") == "blocked"
    ]
    controlled_profile_stops = sum(
        str(row.get("execution_status") or row.get("status") or "") == "controlled_stop"
        for _case, row in blocked_cases
    )
    overall_first_pass_rate = first_pass / len(cases) if cases else 0.0
    in_profile_first_pass_rate = (
        eligible_first_pass / len(eligible_cases) if eligible_cases else 0.0
    )
    checks = {
        "minimum_reviewed_runs_met": reviewed_count >= int(gate.get("minimum_reviewed_runs") or 0),
        "source_changes_zero": sum(int(dict(row.get("safety") or {}).get("source_code_changes") or 0) for row in rows) == 0,
        "handoff_loss_within_limit": len(handoff_codes) <= int(gate.get("maximum_handoff_loss") or 0),
        "unreviewed_runs_within_limit": len(rows) - reviewed_count <= int(gate.get("maximum_pending_reviews") or 0),
        "first_pass_rate_met": overall_first_pass_rate >= float(gate.get("minimum_first_pass_rate") or 0.0),
        "in_profile_first_pass_rate_met": (
            bool(eligible_cases)
            and in_profile_first_pass_rate >= float(gate.get("minimum_first_pass_rate") or 0.0)
        ),
        "review_digests_valid": all(
            row.get("evidence_digest")
            and dict(row.get("human_review") or {}).get("evidence_digest") == row.get("evidence_digest")
            and pilot_run_digest(row) == row.get("evidence_digest")
            for row in reviewed
        ),
    }
    hard_gate_failed = not all(
        checks[name] for name in (
            "source_changes_zero",
            "handoff_loss_within_limit",
            "unreviewed_runs_within_limit",
            "review_digests_valid",
        )
    )
    enough = checks["minimum_reviewed_runs_met"]
    status = "attention_required" if hard_gate_failed or (enough and not all(checks.values())) else (
        "healthy" if all(checks.values()) else "insufficient_observations"
    )
    return {
        "artifact_type": "PilotTelemetryReport",
        "schema_version": "pilot_telemetry.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile_id": policy.get("profile_id"),
        "status": status,
        "checks": checks,
        "summary": {
            "run_count": len(rows),
            "reviewed_run_count": reviewed_count,
            "pending_review_count": len(rows) - reviewed_count,
            "approved_run_count": sum(row.get("status") == "observed_approved" for row in rows),
            "rework_run_count": sum(row.get("status") == "observed_rework" for row in rows),
            "stopped_run_count": sum(row.get("status") == "observed_stopped" for row in rows),
            "case_count": len(cases),
            "first_pass_rate": round(overall_first_pass_rate, 4),
            "in_profile_first_pass_rate": round(in_profile_first_pass_rate, 4),
            "admission_coverage_rate": round(len(eligible_cases) / len(cases), 4) if cases else 0.0,
            "controlled_stop_precision": round(
                controlled_profile_stops / len(blocked_cases), 4
            ) if blocked_cases else 1.0,
            "profile_eligible_case_count": len(eligible_cases),
            "out_of_profile_case_count": len(blocked_cases),
            "handoff_loss_count": len(handoff_codes),
            "controlled_stop_count": sum(
                row.get("execution_status", row.get("status")) == "controlled_stop"
                for row in rows
            ),
            "case_needs_review_count": sum(case.get("status") != "ok" for case in cases),
            "source_code_changes": sum(int(dict(row.get("safety") or {}).get("source_code_changes") or 0) for row in rows),
        },
        "handoff_loss_by_check": {
            code: handoff_codes.count(code) for code in sorted(set(handoff_codes))
        },
        "run_ids": [row.get("run_id") for row in rows],
        "policy": gate,
        "safety": {"source_apply_allowed": False, "automatic_approval_allowed": False},
    }


def build_pilot_review_queue(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    items = []
    for raw in records:
        record = dict(raw)
        case = dict(next(iter(record.get("cases") or []), {}))
        admission = dict(case.get("admission") or {})
        admission_blockers = list(admission.get("blocking_reasons") or [])
        failed = list(case.get("failed_checks") or [])
        if record.get("execution_status") == "awaiting_human_review":
            recommendation = "approve"
            reason = "full_chain_and_profile_admission_passed"
        elif admission.get("status") == "blocked":
            recommendation = "stop"
            reason = "outside_current_pilot_profile"
        else:
            recommendation = "rework"
            reason = "executable_or_quality_gate_needs_rework"
        items.append({
            "run_id": record.get("run_id"),
            "project": case.get("project"),
            "run_record": record.get("report_path"),
            "execution_status": record.get("execution_status"),
            "quality_score": case.get("quality_score"),
            "failed_checks": failed,
            "admission_status": admission.get("status"),
            "admission_blocking_reasons": admission_blockers,
            "recommended_decision": recommendation,
            "recommendation_reason": reason,
            "allowed_decisions": ["approve", "rework", "stop"],
            "evidence_digest": record.get("evidence_digest"),
            "decision_authority": "human",
        })
    return {
        "artifact_type": "PilotReviewQueueReport",
        "schema_version": "pilot_review_queue.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "awaiting_human_decisions" if items else "empty",
        "summary": {
            "decision_count": len(items),
            "recommended_approve": sum(row["recommended_decision"] == "approve" for row in items),
            "recommended_rework": sum(row["recommended_decision"] == "rework" for row in items),
            "recommended_stop": sum(row["recommended_decision"] == "stop" for row in items),
        },
        "items": items,
        "policy": {"automatic_decisions_allowed": False, "source_apply_allowed": False},
    }
def pilot_run_digest(record: dict[str, Any]) -> str:
    payload = {
        key: value for key, value in record.items()
        if key not in {
            "status", "evidence_digest", "human_review", "report_path",
            "review_report_path", "reviewed_record_source",
        }
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _run_id(report: dict[str, Any]) -> str:
    projects = ",".join(str(row.get("project") or "") for row in report.get("cases") or [])
    seed = "|".join((
        str(report.get("report_path") or report.get("generated_at") or "inline"),
        projects,
    ))
    return "pilot_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
