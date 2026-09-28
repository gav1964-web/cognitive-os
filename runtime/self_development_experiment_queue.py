"""Bind prospective candidates to certified lanes before experiments exist."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .evidence_ledger import verify_evidence_entry
from .narrow_type_certification import verify_narrow_type_certification


TARGET_METRICS = {
    "recognition_gap": "recognition_accuracy",
    "classification_contradiction": "recognition_accuracy",
    "no_safe_candidate": "safe_candidate_rate",
    "role_handoff_gap": "role_continuity",
    "evaluator_mismatch": "evaluator_agreement",
    "admission_gap": "admission_accuracy",
    "human_rejection": "human_acceptance_rate",
    "false_promotion_readiness": "promotion_precision",
}


def build_self_development_experiment_queue(
    *, root: Path, detection: dict[str, Any], certification_receipt: str
) -> dict[str, Any]:
    receipt = verify_evidence_entry(root=root, ledger_path=Path(certification_receipt))
    certification = dict(receipt.get("evidence_payload") or {})
    certification_verified = (
        receipt.get("status") == "verified"
        and verify_narrow_type_certification(certification, evidence_root=root)
    )
    detection_checks = dict(detection.get("checks") or {})
    candidates = list(detection.get("candidates") or [])
    detection_verified = (
        detection.get("artifact_type") == "SelfDevelopmentProspectiveDetectionReport"
        and detection.get("status") in {"candidate_detected", "waiting_for_evidence"}
        and (detection.get("status") == "candidate_detected") is bool(candidates)
        and all(detection_checks.values())
        and int(detection.get("candidate_count") or 0) == len(candidates)
        and dict(detection.get("safety") or {}).get("promotion_applied") is False
    )
    certified_types = set(certification.get("project_strata") or []) if certification_verified else set()
    ready, deferred = [], []
    for candidate_value in candidates:
        candidate = dict(candidate_value or {})
        proposal = dict(dict(candidate.get("dossier") or {}).get("proposal") or {})
        classification = dict(proposal.get("classification") or {})
        project_types = set(dict(proposal.get("impact_map") or {}).get("project_types") or [])
        rule_id = str(candidate.get("signature") or "").split(":", 1)[0]
        reasons = []
        if classification.get("class") not in {"L0", "L1"}:
            reasons.append("change_class_outside_bounded_route")
        if not project_types or not project_types.issubset(certified_types):
            reasons.append("project_type_not_certified")
        if rule_id not in TARGET_METRICS:
            reasons.append("target_metric_not_defined")
        row = {
            "proposal_id": proposal.get("proposal_id"),
            "signature": candidate.get("signature"),
            "change_class": classification.get("class"),
            "project_types": sorted(project_types),
            "candidate_digest": _digest(candidate),
        }
        if reasons:
            deferred.append({**row, "status": "deferred", "reasons": reasons})
            continue
        ready.append({
            **row,
            "status": "ready_for_baseline_candidate_experiment",
            "target_metric": TARGET_METRICS[rule_id],
            "required_evidence": [
                "frozen_baseline", "candidate_patch", "unseen_project_holdout",
                "independent_evaluator", "no_role_regression", "generated_stub_gate",
            ],
        })
    checks = {
        "detection_verified": detection_verified,
        "certification_receipt_verified": certification_verified,
        "certified_scope_nonempty": bool(certified_types),
        "no_active_apply": True,
        "no_automatic_promotion": True,
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        status = "blocked"
    elif ready:
        status = "ready_for_experiment"
    elif candidates:
        status = "waiting_for_certified_candidate"
    else:
        status = "waiting_for_candidate"
    body = {
        "artifact_type": "SelfDevelopmentExperimentQueue",
        "schema_version": "self_development_experiment_queue.v1",
        "status": status,
        "checks": checks,
        "failed_checks": failed,
        "detection": {
            "status": detection.get("status"),
            "candidate_count": len(candidates),
            "report_digest": _digest(detection),
        },
        "certification": {
            "receipt": certification_receipt,
            "declared_status": certification.get("status") if certification else "invalid",
            "authority_status": "verified" if certification_verified else "rejected",
            "schema_version": certification.get("schema_version"),
            "project_strata": sorted(certified_types),
        },
        "ready_count": len(ready),
        "ready": ready,
        "deferred_count": len(deferred),
        "deferred": deferred,
        "next_action": _next_action(status),
        "safety": {"source_apply": False, "active_kb_write": False, "promotion_applied": False},
    }
    return {**body, "queue_digest": _digest(body)}


def _next_action(status: str) -> str:
    return {
        "ready_for_experiment": "run_frozen_baseline_candidate_holdout",
        "waiting_for_certified_candidate": "collect_or_certify_matching_project_type",
        "waiting_for_candidate": "collect_new_independent_project_evidence",
        "blocked": "repair_queue_authority_inputs",
    }[status]


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
