from __future__ import annotations

from runtime.role_foundation_excellence import (
    _backlog_pressure,
    _github_spec_semantic_floor,
    _score_project_analyzer,
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


def test_project_analyzer_excellence_does_not_score_penalize_backlog_notes():
    result = _score_project_analyzer(
        {
            "architect_local": {
                "summary": {"fact_recall": 1.0, "fact_precision": 1.0, "backlog_items": 0},
                "cases": [{"fact_score": {"recall": 1.0, "precision": 1.0}}],
            },
            "architect_external": {
                "summary": {"fact_recall": 0.98, "fact_precision": 0.97, "backlog_items": 7},
                "cases": [{"fact_score": {"recall": 0.94, "precision": 0.94}}],
            },
            "architect_github": {
                "project_count": 2,
                "summary": {"ok": 2, "avg_quality_score": 1.0},
                "cases": [{"quality_score": 1.0, "summary": {"project_report_quality": 1.0}}],
            },
        },
        target_score=9.2,
    )

    assert result["score"] == 9.4
    assert result["target_met"] is True
    assert result["metrics"]["backlog_is_score_blocking"] is False


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


def test_target_quality_accepts_resource_displayhook_and_protocol_state_targets():
    for target in (
        "certifi/core.py:contents",
        "src/werkzeug/debug/console.py:displayhook",
        "h11/_connection.py:our_state",
    ):
        quality = semantic_target_quality_report(
            target,
            ranked_candidates=[target],
            source_evidence=[target],
            selection_reason="pure transform candidate",
        )
        assert quality["status"] == "strong"


def test_target_quality_recognizes_foundation_holdout_contract_families():
    for target in (
        "returns/contrib/mypy/_typeops/visitor.py:translate_kind_instance",
        "pelican/settings.py:configure_settings",
        "IPython/core/guarded_eval.py:eval_node",
        "xarray/core/parallel.py:map_blocks",
        "packages/zarr-indexing/src/zarr_indexing/transform.py:_apply_oindex",
        "zmq/backend/cython/_zmq.py:zmq_poll",
        "nbconvert/exporters/webpdf.py:run_playwright",
    ):
        quality = semantic_target_quality_report(
            target,
            ranked_candidates=[target],
            source_evidence=[target],
            selection_reason="pure transform candidate",
        )
        assert quality["status"] == "strong"
        assert quality["score"] >= 92


def test_target_quality_scores_parser_combinator_helper_as_reviewable_contract():
    target = "pyparsing/helpers.py:one_of"

    quality = semantic_target_quality_report(
        target,
        ranked_candidates=[target],
        source_evidence=[target],
        selection_reason="pure transform candidate",
    )

    assert quality["status"] == "acceptable"
    assert quality["score"] == 84
    assert "parser_combinator_helper_boundary" in quality["semantic_profile_ids"]


def test_target_quality_profiles_sql_lint_fix_parsed_tree_contract():
    target = "src/sqlfluff/core/linter/linter.py:lint_fix_parsed"

    quality = semantic_target_quality_report(
        target,
        ranked_candidates=[target],
        source_evidence=[target],
        selection_reason="pure transform candidate",
    )

    assert quality["status"] == "strong"
    assert quality["score"] >= 98
    assert "sql_lint_fix_parsed_tree_boundary" in quality["semantic_profile_ids"]


def test_target_quality_keeps_response_boundary_acceptable_not_strong():
    target = "app.py:make_response"

    quality = semantic_target_quality_report(
        target,
        ranked_candidates=[target],
        source_evidence=[target],
        selection_reason="pure transform candidate",
    )

    assert quality["status"] == "acceptable"
