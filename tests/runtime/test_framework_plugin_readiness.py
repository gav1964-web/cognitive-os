from __future__ import annotations

from runtime.framework_plugin_readiness import REQUIRED_ROLES, build_framework_plugin_readiness


def _evaluation(score: float = 9.7) -> dict:
    return {"cells": [{
        "role_id": role, "project_stratum": "framework_plugin_build",
        "score": score, "maturity": "mature",
    } for role in REQUIRED_ROLES]}


def _detection(count: int = 3) -> dict:
    return {
        "minimum_independent_projects": 3,
        "candidates": [{
            "signature": "recognition_gap:architecture:recognition_gap:framework_plugin_build",
            "independent_project_count": count,
        }],
    }


def test_mature_framework_candidate_still_requires_certification_holdout() -> None:
    report = build_framework_plugin_readiness(
        evaluation=_evaluation(), detection=_detection()
    )

    assert report["status"] == "holdout_required"
    assert report["checks"]["all_role_scores_at_target"] is True
    assert report["checks"]["prospective_candidate_detected"] is True
    assert report["checks"]["independent_certification_holdout"] is False
    assert report["certification_granted"] is False


def test_weak_role_keeps_framework_lane_at_evidence_required() -> None:
    report = build_framework_plugin_readiness(
        evaluation=_evaluation(9.6), detection=_detection()
    )

    assert report["status"] == "evidence_required"
    assert report["checks"]["all_role_scores_at_target"] is False
