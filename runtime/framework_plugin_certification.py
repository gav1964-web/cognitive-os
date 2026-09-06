"""Certify the framework/plugin lane from durable independent evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .evidence_ledger import verify_evidence_entry
from .framework_plugin_readiness import REQUIRED_ROLES


REQUIRED_RECEIPT_CHECKS = {
    "independent_holdout",
    "lineage_disjoint",
    "no_role_regression",
    "role_chain_continuity",
    "generated_stub_gate",
    "inputs_digest_bound",
}


def build_framework_plugin_certification(
    *,
    evaluation: dict[str, Any],
    evidence_root: Path,
    holdout_receipt: str | None = None,
    target_score: float = 9.7,
) -> dict[str, Any]:
    cells = {
        str(row.get("role_id")): dict(row)
        for row in evaluation.get("cells") or []
        if row.get("project_stratum") == "framework_plugin_build"
    }
    cell_checks = []
    for role in REQUIRED_ROLES:
        cell = cells.get(role, {})
        score = cell.get("score")
        checks = {
            "measured": isinstance(score, (int, float)),
            "score_at_target": isinstance(score, (int, float))
            and float(score) >= target_score,
            "maturity_demonstrated": cell.get("maturity") == "mature",
            "evidence_complete": not list(
                cell.get("evidence_gaps") or cell.get("gaps") or []
            ),
            "dedicated_lane_ready": cell.get("maturity") == "mature"
            and not list(cell.get("evidence_gaps") or []),
        }
        cell_checks.append({
            "role_id": role,
            "score": score,
            "status": "passed" if all(checks.values()) else "failed",
            "checks": checks,
        })

    receipt_checks = {name: False for name in sorted(REQUIRED_RECEIPT_CHECKS)}
    receipt_checks.update({
        "ledger_receipt_verified": False,
        "holdout_report_passed": False,
        "zero_generated_stubs": False,
        "multiple_holdout_lineages": False,
    })
    receipt_verification: dict[str, Any] = {"status": "not_provided"}
    if holdout_receipt:
        receipt_verification = verify_evidence_entry(
            root=evidence_root, ledger_path=Path(holdout_receipt)
        )
        payload = dict(receipt_verification.get("evidence_payload") or {})
        evidence_checks = dict(payload.get("checks") or {})
        provenance = dict(payload.get("holdout_provenance") or {})
        receipt_checks.update({
            name: evidence_checks.get(name) is True
            for name in REQUIRED_RECEIPT_CHECKS
        })
        receipt_checks.update({
            "ledger_receipt_verified": receipt_verification.get("status") == "verified",
            "holdout_report_passed": payload.get("artifact_type")
            == "FrameworkPluginHoldoutEvidence"
            and payload.get("status") == "passed",
            "zero_generated_stubs": int(payload.get("generated_stub_count") or 0) == 0,
            "multiple_holdout_lineages": int(provenance.get("source_lineages") or 0) > 1,
        })

    cells_passed = bool(cell_checks) and all(
        row["status"] == "passed" for row in cell_checks
    )
    passed = cells_passed and all(receipt_checks.values())
    body = {
        "artifact_type": "FrameworkPluginCertification",
        "schema_version": "framework_plugin_certification.v1",
        "status": "certified" if passed else "evidence_required",
        "project_stratum": "framework_plugin_build",
        "target_score": target_score,
        "required_roles": list(REQUIRED_ROLES),
        "cell_checks": cell_checks,
        "holdout_receipt": holdout_receipt,
        "receipt_status": receipt_verification.get("status"),
        "receipt_checks": receipt_checks,
        "failed_cell_roles": [
            row["role_id"] for row in cell_checks if row["status"] != "passed"
        ],
        "failed_receipt_checks": [
            name for name, value in receipt_checks.items() if not value
        ],
        "promotion_eligible": passed,
        "promotion_applied": False,
        "next_action": "certification_complete" if passed else (
            "run_fresh_framework_owner_holdout_with_stub_and_regression_receipts"
        ),
    }
    return {**body, "certificate_digest": _digest(body)}


def verify_framework_plugin_certification(value: dict[str, Any]) -> bool:
    body = {key: item for key, item in value.items() if key != "certificate_digest"}
    return (
        value.get("artifact_type") == "FrameworkPluginCertification"
        and value.get("schema_version") == "framework_plugin_certification.v1"
        and value.get("status") == "certified"
        and value.get("promotion_eligible") is True
        and value.get("promotion_applied") is False
        and all(row.get("status") == "passed" for row in value.get("cell_checks") or [])
        and all(dict(value.get("receipt_checks") or {}).values())
        and value.get("certificate_digest") == _digest(body)
    )


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
