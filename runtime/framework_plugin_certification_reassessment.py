"""Reassess and revoke obsolete framework/plugin certification authority."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .evidence_ledger import verify_evidence_entry


def build_framework_plugin_certification_reassessment(
    *,
    root: Path,
    prior_certificate_receipt: str,
    holdout_reassessment: dict[str, Any],
    role_regression: dict[str, Any],
) -> dict[str, Any]:
    prior = verify_evidence_entry(
        root=root, ledger_path=Path(prior_certificate_receipt)
    )
    prior_payload = dict(prior.get("evidence_payload") or {})
    checks = {
        "prior_receipt_verified": prior.get("status") == "verified",
        "prior_certificate_is_obsolete_v1": prior_payload.get("artifact_type")
        == "FrameworkPluginCertification"
        and prior_payload.get("schema_version") == "framework_plugin_certification.v1",
        "semantic_reassessment_is_v2": holdout_reassessment.get("artifact_type")
        == "FrameworkPluginHoldoutEvidence"
        and holdout_reassessment.get("schema_version")
        == "framework_plugin_holdout_evidence.v2",
        "semantic_quality_not_demonstrated": dict(
            holdout_reassessment.get("checks") or {}
        ).get("semantic_role_quality")
        is False,
        "role_artifacts_now_auditable": dict(
            holdout_reassessment.get("checks") or {}
        ).get("role_artifacts_auditable")
        is True,
        "development_not_demonstrated": dict(
            holdout_reassessment.get("checks") or {}
        ).get("project_development_evaluated")
        is False,
        "unrelated_role_matrix_preserved": role_regression.get("status") == "passed"
        and int(role_regression.get("regression_count") or 0) == 0,
    }
    revoked = all(checks.values())
    body = {
        "artifact_type": "FrameworkPluginCertificationReassessment",
        "schema_version": "framework_plugin_certification_reassessment.v1",
        "status": "revoked" if revoked else "review_required",
        "prior_certificate_receipt": prior_certificate_receipt,
        "prior_certificate_digest": prior_payload.get("certificate_digest"),
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "reason_codes": [
            "constant_role_scores_without_semantic_authority",
            "artifact_presence_mistaken_for_role_quality",
            "verification_only_holdout_mistaken_for_project_development",
        ] if revoked else [],
        "affected_scope": {
            "framework_plugin_certification": "revoked" if revoked else "under_review",
            "runtime_functionality": "not_revoked",
            "historical_evidence": "retained_immutable",
            "role_maturity_matrix": "retained_not_certification_authority",
        },
        "promotion_eligible": False,
        "promotion_applied": False,
        "next_action": "run_semantic_ground_truth_holdout" if revoked else "complete_reassessment_inputs",
    }
    return {**body, "reassessment_digest": _digest(body)}


def verify_framework_plugin_certification_reassessment(value: dict[str, Any]) -> bool:
    body = {key: item for key, item in value.items() if key != "reassessment_digest"}
    return (
        value.get("artifact_type") == "FrameworkPluginCertificationReassessment"
        and value.get("schema_version") == "framework_plugin_certification_reassessment.v1"
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
