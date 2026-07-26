from __future__ import annotations

from runtime.role_foundation_excellence import (
    _backlog_pressure,
    _github_spec_semantic_floor,
    _semantic_score,
    _strong_ratio,
)
from runtime.target_quality import semantic_target_quality_report


def test_semantic_score_rewards_strong_and_discounts_acceptable_targets():
    summary = {
        "semantic_strong": 7,
        "semantic_acceptable": 3,
        "semantic_suspicious": 0,
        "semantic_poor": 0,
    }

    assert _semantic_score(summary) == 0.865
    assert _strong_ratio(summary) == 0.7


def test_semantic_score_penalizes_suspicious_targets():
    summary = {
        "semantic_strong": 7,
        "semantic_acceptable": 2,
        "semantic_suspicious": 1,
        "semantic_poor": 0,
    }

    assert _semantic_score(summary) == 0.83


def test_backlog_pressure_caps_at_one():
    assert _backlog_pressure({"backlog_items": 4}, {"backlog_items": 8}) == 0.6
    assert _backlog_pressure({"backlog_items": 30}) == 1.0


def test_spec_writer_excellence_uses_worst_project_floor():
    report = {
        "cases": [
            {
                "status": "ok",
                "quality_score": 1.0,
                "semantic_target_quality": {"score": 100, "status": "strong"},
            },
            {
                "status": "ok",
                "quality_score": 1.0,
                "semantic_target_quality": {"score": 84, "status": "acceptable"},
            },
        ]
    }

    assert _github_spec_semantic_floor(report) == 0.84


def test_target_quality_treats_factory_query_and_make_contracts_as_strong():
    for target in (
        "httpcore/_async/connection_pool.py:create_connection",
        "yarl/_query.py:query_var",
        "lib/matplotlib/image.py:_make_image",
        "rq/job.py:create",
    ):
        quality = semantic_target_quality_report(
            target,
            ranked_candidates=[target],
            source_evidence=[target],
            selection_reason="pure transform candidate",
        )
        assert quality["status"] == "strong"


def test_target_quality_keeps_response_boundary_acceptable_not_strong():
    target = "src/flask/app.py:make_response"

    quality = semantic_target_quality_report(
        target,
        ranked_candidates=[target],
        source_evidence=[target],
        selection_reason="pure transform candidate",
    )

    assert quality["status"] == "acceptable"
