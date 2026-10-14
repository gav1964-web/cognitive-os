"""Assess framework/plugin readiness without granting certification."""

from __future__ import annotations

import hashlib
import json
from typing import Any


REQUIRED_ROLES = ["project_analyzer", "architect", "spec_writer", "implementer", "tester", "reviewer"]


def build_framework_plugin_readiness(
    *, evaluation: dict[str, Any], detection: dict[str, Any], target_score: float = 9.7
) -> dict[str, Any]:
    cells = {
        str(row.get("role_id")): dict(row)
        for row in evaluation.get("cells") or []
        if row.get("project_stratum") == "framework_plugin_build"
    }
    role_checks = [{
        "role_id": role,
        "score": cells.get(role, {}).get("score"),
        "maturity": cells.get(role, {}).get("maturity"),
        "passed": isinstance(cells.get(role, {}).get("score"), (int, float))
        and float(cells[role]["score"]) >= target_score
        and cells[role].get("maturity") == "mature",
    } for role in REQUIRED_ROLES]
    candidates = [
        dict(row) for row in detection.get("candidates") or []
        if "framework_plugin_build" in str(row.get("signature") or "")
    ]
    checks = {
        "all_role_scores_at_target": all(row["passed"] for row in role_checks),
        "prospective_candidate_detected": bool(candidates),
        "candidate_independence_threshold_met": bool(candidates)
        and all(int(row.get("independent_project_count") or 0) >= int(detection.get("minimum_independent_projects") or 3) for row in candidates),
        "independent_certification_holdout": False,
        "generated_stub_gate_receipt": False,
        "no_role_regression_receipt": False,
        "no_automatic_certification": True,
    }
    body = {
        "artifact_type": "FrameworkPluginReadinessReport",
        "schema_version": "framework_plugin_readiness.v1",
        "status": "holdout_required" if all(checks[name] for name in (
            "all_role_scores_at_target", "prospective_candidate_detected", "candidate_independence_threshold_met"
        )) else "evidence_required",
        "target_score": target_score,
        "role_checks": role_checks,
        "prospective_candidates": candidates,
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "next_action": "run_framework_plugin_independent_holdout_and_stub_audit",
        "certification_granted": False,
        "promotion_applied": False,
    }
    return {**body, "report_digest": _digest(body)}


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
