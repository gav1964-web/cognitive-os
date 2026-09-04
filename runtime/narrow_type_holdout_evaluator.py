"""Evaluate real narrow-lane holdout evidence without inferring missing gates."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .role_project_type_evaluation_policy import load_role_project_type_policy


def evaluate_narrow_type_holdout(
    *,
    evaluation: dict[str, Any],
    role_pipeline_report: dict[str, Any],
    stub_audit: dict[str, Any] | None = None,
    input_provenance: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rules = policy or load_role_project_type_policy()
    lane = dict(dict(rules.get("development_priority") or {}).get("current_lane") or {})
    required = {
        (str(role), str(project_type))
        for project_type in lane.get("project_strata") or []
        for role in lane.get("required_roles") or []
    }
    cells = {
        (str(row.get("role_id")), str(row.get("project_stratum"))): dict(row)
        for row in evaluation.get("cells") or []
        if isinstance(row, dict)
    }
    selected = [cells.get(identity, {}) for identity in sorted(required)]
    chain = dict(dict(role_pipeline_report.get("summary") or {}).get("role_chain") or {})
    audit = dict(stub_audit or {})
    generated_stub_count = (
        int(audit["generated_stub_count"])
        if isinstance(audit.get("generated_stub_count"), int)
        else None
    )
    target_score = float(lane.get("target_score") or 9.7)
    provenance = dict(input_provenance or {})
    required_inputs = {"evaluation", "role_pipeline", "stub_audit"}
    core_inputs = [dict(provenance.get(name) or {}) for name in sorted(required_inputs)]
    blind_receipts = [dict(row) for row in provenance.get("blind_reports") or []]
    checks = {
        "all_required_cells_present": len(selected) == len(required) and all(selected),
        "scores_at_promotion_target": all(
            isinstance(row.get("score"), (int, float)) and float(row["score"]) >= target_score
            for row in selected
        ),
        "cells_promotion_eligible": all(row.get("promotion_eligible") is True for row in selected),
        "independent_holdout": all(int(row.get("blind_project_count") or 0) >= 2 for row in selected),
        "lineage_disjoint": all(row.get("lineage_disjoint") is True for row in selected),
        "no_role_regression": all(not row.get("evidence_gaps") for row in selected),
        "role_chain_continuity": int(chain.get("handoff_loss_count") or 0) == 0
        and float(chain.get("minimum_interaction_score") or 0.0) >= 0.9,
        "generated_stub_gate": audit.get("artifact_type") == "GeneratedFunctionStubAudit"
        and audit.get("status") == "passed"
        and generated_stub_count == 0,
        "independent_evaluator": True,
        "inputs_digest_bound": required_inputs.issubset(provenance)
        and all(row.get("verified") is True for row in core_inputs),
    }
    lineages = {
        lineage
        for row in selected
        for lineage in row.get("blind_source_lineages") or []
    }
    source_reports = [
        str(row.get("path")) for row in evaluation.get("sources") or [] if row.get("blind") is True
    ]
    audited_reports = {str(path).replace("\\", "/").lower() for path in dict(audit.get("report_digests") or {})}
    required_reports = {path.replace("\\", "/").lower() for path in source_reports}
    audit_covers_holdout = bool(required_reports) and audited_reports == required_reports
    audited_digests = set(dict(audit.get("report_digests") or {}).values())
    receipt_digests = {
        row.get("content_digest") for row in blind_receipts if row.get("verified") is True
    }
    blind_inputs_durable = bool(audited_digests) and receipt_digests == audited_digests
    checks["stub_audit_covers_holdout"] = audit_covers_holdout
    checks["generated_stub_gate"] = checks["generated_stub_gate"] and audit_covers_holdout
    checks["blind_inputs_durable"] = blind_inputs_durable
    body = {
        "artifact_type": "NarrowTypeHoldoutEvidence",
        "schema_version": "narrow_type_holdout_evidence.v1",
        "status": "passed" if all(checks.values()) else "evidence_required",
        "lane_id": lane.get("id"),
        "target_score": target_score,
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "generated_stub_count": generated_stub_count,
        "holdout_provenance": {
            "selection_digest": _digest(source_reports),
            "case_count": min((int(row.get("blind_project_count") or 0) for row in selected), default=0),
            "source_lineages": len(lineages),
            "source_report_count": len(source_reports),
        },
        "role_chain_report": role_pipeline_report.get("report_path"),
        "stub_audit": audit or {"status": "not_provided"},
        "input_provenance": provenance,
        "source_apply": False,
        "promotion_applied": False,
    }
    return {**body, "evidence_digest": _digest(body)}


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
