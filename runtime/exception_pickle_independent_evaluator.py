"""Independent evaluator review for exception pickle reconstruction promotion."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def review_exception_pickle_promotion(
    *,
    root: Path,
    readiness_path: Path,
    holdout_path: Path,
    shadow_path: Path,
    minimum_holdout_projects: int = 25,
) -> dict[str, Any]:
    """Review promotion evidence without applying KB or source changes."""
    root = root.resolve()
    readiness = _read_json(root, readiness_path)
    holdout = _read_json(root, holdout_path)
    shadow = _read_json(root, shadow_path)
    supervised_projects = {
        str(row.get("project") or "")
        for row in dict(readiness.get("evidence") or {}).get("reports") or []
        if isinstance(row, dict)
    }
    autonomous_reports = [
        dict(row)
        for row in dict(readiness.get("evidence") or {}).get("autonomous_reports") or []
        if isinstance(row, dict)
    ]
    candidate = dict(shadow.get("candidate") or {})
    checks = {
        "readiness_allows_review": readiness.get("promotion_review_allowed") is True,
        "readiness_has_autonomous_evidence": dict(readiness.get("checks") or {}).get(
            "autonomous_evidence_available"
        )
        is True,
        "readiness_does_not_promote_kb": readiness.get("kb_promotion_allowed") is False,
        "holdout_transaction_ready": holdout.get("status") == "holdout_ready",
        "holdout_has_independent_breadth": int(holdout.get("holdout_project_count") or 0)
        >= minimum_holdout_projects,
        "shadow_is_autonomous_verified": shadow.get("status") == "autonomous_verified_shadow",
        "shadow_counts_as_autonomous": shadow.get(
            "counts_as_autonomous_verified_transformation"
        )
        is True,
        "shadow_semantic_replay_passed": dict(
            shadow.get("project_native_semantic_replay") or {}
        ).get("status")
        == "passed",
        "shadow_project_independent": str(candidate.get("project") or "")
        not in supervised_projects,
        "operator_is_exact": shadow.get("operator_id")
        == "preserve_exception_constructor_reconstruction",
        "source_apply_absent": shadow.get("source_apply") is False
        and holdout.get("source_apply") is False,
        "kb_promotion_absent": shadow.get("kb_promotion") is False
        and holdout.get("kb_promotion") is False,
        "readiness_autonomous_report_matches_shadow": any(
            row.get("report") == _relative(root, shadow_path)
            and row.get("verified") is True
            for row in autonomous_reports
        ),
    }
    return {
        "artifact_type": "ExceptionPickleIndependentEvaluatorReview",
        "schema_version": "exception_pickle_independent_evaluator_review.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if all(checks.values()) else "blocked",
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "evidence": {
            "readiness": _relative(root, readiness_path),
            "holdout": _relative(root, holdout_path),
            "shadow": _relative(root, shadow_path),
            "supervised_projects": sorted(supervised_projects - {""}),
            "autonomous_project": candidate.get("project"),
            "autonomous_target": candidate.get("target"),
            "holdout_project_count": holdout.get("holdout_project_count"),
            "holdout_candidate_count": holdout.get("holdout_candidate_count"),
        },
        "source_apply": False,
        "kb_promotion": False,
    }


def _read_json(root: Path, path: Path) -> dict[str, Any]:
    resolved = path if path.is_absolute() else root / path
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact must be an object: {resolved}")
    return payload


def _relative(root: Path, path: Path) -> str:
    resolved = path if path.is_absolute() else root / path
    return resolved.resolve().relative_to(root).as_posix()
