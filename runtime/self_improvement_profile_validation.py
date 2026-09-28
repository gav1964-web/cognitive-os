"""Independent validation report for a staged semantic profile template."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_profile_validation_report(
    candidate: dict[str, Any], observations: list[dict[str, Any]], *, target_score: float
) -> dict[str, Any]:
    proposed = dict(candidate.get("proposed_record") or {})
    family = str(proposed.get("contract_family") or proposed.get("id") or "")
    source_cases = list(candidate.get("source_cases") or [])
    confirmed_training = [row for row in source_cases if row.get("status") == "confirmed"]
    recognized = [row for row in observations if row.get("recognized_family") == family]
    independent_improvements = [
        row for row in recognized
        if row.get("training_status") == "candidate_improvement_confirmed" and float(row.get("score_delta") or 0) > 0
    ]
    confirmed_count = len(confirmed_training) + len(independent_improvements)
    return {
        "artifact_type": "SelfImprovementProfileValidationReport",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidate_id": candidate.get("candidate_id"),
        "contract_family": family,
        "target_score": target_score,
        "recognition_case_count": len(recognized),
        "candidate_improvement_case_count": confirmed_count,
        "required_candidate_improvement_cases": 3,
        "status": "ready_for_review" if confirmed_count >= 3 else "collect_more_improvement_cases",
        "observations": observations,
        "evidence_policy": {
            "recognition_is_not_improvement": True,
            "already_at_target_does_not_confirm_treatment": True,
            "candidate_status_mutated": False,
        },
    }
