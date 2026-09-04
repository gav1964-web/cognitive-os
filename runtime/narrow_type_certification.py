"""Certify narrow role/project-type cells from independent ledger evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .evidence_ledger import verify_evidence_entry
from .role_project_type_evaluation_policy import load_role_project_type_policy


def build_narrow_type_certification(
    *,
    evaluation: dict[str, Any],
    evidence_root: Path,
    holdout_receipt: str,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rules = policy or load_role_project_type_policy()
    lane = dict(dict(rules.get("development_priority") or {}).get("current_lane") or {})
    target_score = float(lane.get("target_score") or rules.get("promotion_score") or 9.7)
    strata = [str(value) for value in lane.get("project_strata") or []]
    roles = [str(value) for value in lane.get("required_roles") or []]
    cells = {
        (str(row.get("role_id")), str(row.get("project_stratum"))): dict(row)
        for row in evaluation.get("cells") or []
        if isinstance(row, dict)
    }
    cell_checks = []
    for stratum in strata:
        for role in roles:
            cell = cells.get((role, stratum), {})
            score = cell.get("score")
            checks = {
                "measured": isinstance(score, (int, float)),
                "score_at_least_9_7": isinstance(score, (int, float)) and float(score) >= target_score,
                "evidence_complete": not list(cell.get("evidence_gaps") or cell.get("gaps") or []),
                "promotion_eligible": cell.get("promotion_eligible") is True,
            }
            cell_checks.append({
                "role_id": role,
                "project_stratum": stratum,
                "score": score,
                "status": "passed" if all(checks.values()) else "failed",
                "checks": checks,
            })
    receipt = verify_evidence_entry(root=evidence_root, ledger_path=Path(holdout_receipt))
    payload = dict(receipt.get("evidence_payload") or {})
    evidence_checks = dict(payload.get("checks") or {})
    holdout = dict(payload.get("holdout_provenance") or {})
    receipt_checks = {
        "ledger_receipt_verified": receipt.get("status") == "verified",
        "holdout_report_passed": payload.get("status") == "passed",
        "independent_holdout": evidence_checks.get("independent_holdout") is True,
        "lineage_disjoint": evidence_checks.get("lineage_disjoint") is True,
        "no_role_regression": evidence_checks.get("no_role_regression") is True,
        "role_chain_continuity": evidence_checks.get("role_chain_continuity") is True,
        "generated_stub_gate": evidence_checks.get("generated_stub_gate") is True
        and int(payload.get("generated_stub_count") or 0) == 0,
        "inputs_digest_bound": evidence_checks.get("inputs_digest_bound") is True,
        "multiple_holdout_lineages": int(holdout.get("source_lineages") or 0) > 1,
    }
    all_cells_passed = bool(cell_checks) and all(row["status"] == "passed" for row in cell_checks)
    passed = all_cells_passed and all(receipt_checks.values())
    body = {
        "artifact_type": "NarrowTypeCertification",
        "schema_version": "narrow_type_certification.v1",
        "status": "certified" if passed else "evidence_required",
        "lane_id": lane.get("id"),
        "target_score": target_score,
        "project_strata": strata,
        "required_roles": roles,
        "cell_checks": cell_checks,
        "receipt": holdout_receipt,
        "receipt_checks": receipt_checks,
        "broad_strata": {
            "status": "deferred",
            "project_strata": list(
                dict(dict(rules.get("development_priority") or {}).get("deferred_lane") or {})
                .get("project_strata") or []
            ),
        },
        "promotion_eligible": passed,
        "promotion_applied": False,
    }
    return {**body, "certificate_digest": _digest(body)}


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
