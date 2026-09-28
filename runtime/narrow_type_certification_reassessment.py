"""Revoke obsolete narrow certification without discarding execution evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .evidence_ledger import verify_evidence_entry


def build_narrow_type_certification_reassessment(
    *, root: Path, certificate_receipt: str, holdout_receipt: str
) -> dict[str, Any]:
    certificate = verify_evidence_entry(
        root=root, ledger_path=Path(certificate_receipt)
    )
    holdout = verify_evidence_entry(root=root, ledger_path=Path(holdout_receipt))
    certificate_payload = dict(certificate.get("evidence_payload") or {})
    holdout_payload = dict(holdout.get("evidence_payload") or {})
    holdout_checks = dict(holdout_payload.get("checks") or {})
    checks = {
        "certificate_receipt_verified": certificate.get("status") == "verified",
        "holdout_receipt_verified": holdout.get("status") == "verified",
        "certificate_is_obsolete_v1": certificate_payload.get("schema_version")
        == "narrow_type_certification.v1",
        "holdout_is_obsolete_v1": holdout_payload.get("schema_version")
        == "narrow_type_holdout_evidence.v1",
        "semantic_role_quality_missing": "semantic_role_quality" not in holdout_checks,
        "role_artifact_audit_missing": "role_artifacts_auditable" not in holdout_checks,
        "project_development_evidence_missing": "project_development_evaluated"
        not in holdout_checks,
    }
    revoked = all(checks.values())
    body = {
        "artifact_type": "NarrowTypeCertificationReassessment",
        "schema_version": "narrow_type_certification_reassessment.v1",
        "status": "revoked" if revoked else "review_required",
        "certificate_receipt": certificate_receipt,
        "holdout_receipt": holdout_receipt,
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "reason_codes": [
            "first_three_role_scores_not_semantically_auditable",
            "derived_mutation_probe_not_project_understanding_evidence",
        ] if revoked else [],
        "affected_scope": {
            "narrow_six_role_certification": "revoked" if revoked else "under_review",
            "downstream_mutation_evidence": "retained",
            "runtime_functionality": "not_revoked",
            "historical_evidence": "retained_immutable",
        },
        "promotion_eligible": False,
        "promotion_applied": False,
        "next_action": "run_narrow_semantic_ground_truth_holdout" if revoked else "complete_reassessment_inputs",
    }
    return {**body, "reassessment_digest": _digest(body)}


def verify_narrow_type_certification_reassessment(value: dict[str, Any]) -> bool:
    body = {key: item for key, item in value.items() if key != "reassessment_digest"}
    return (
        value.get("artifact_type") == "NarrowTypeCertificationReassessment"
        and value.get("schema_version") == "narrow_type_certification_reassessment.v1"
        and value.get("status") == "revoked"
        and value.get("promotion_eligible") is False
        and all(dict(value.get("checks") or {}).values())
        and value.get("reassessment_digest") == _digest(body)
    )


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
