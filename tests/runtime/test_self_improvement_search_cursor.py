import json
from pathlib import Path

from runtime.self_improvement_search_cursor import (
    advance_query_cursors, build_round_search_plan,
    prior_query_page_ends, prior_search_page_end,
)


def test_search_cursor_survives_plan_version_change(tmp_path: Path):
    directory = tmp_path / "artifacts" / "self_improvement"
    directory.mkdir(parents=True)
    report = {
        "plan": {
            "plan_version": "old",
            "failure_class": "side_effectful_target",
            "portable_signature": "side_effectful_target|memory_state|void_side_effect",
            "maximum_search_pages": 2,
            "queries": ["state management"],
        },
        "discovery_rounds": [{"round": 1}, {"round": 2}, {"round": 3}],
    }
    (directory / "hypothesis_validation_old.json").write_text(
        json.dumps(report), encoding="utf-8"
    )
    plan = {
        "plan_version": "new",
        "failure_class": "side_effectful_target",
        "portable_signature": "side_effectful_target|memory_state|void_side_effect",
        "queries": ["state management"],
    }

    assert prior_search_page_end(tmp_path, plan) == 6
    plan["queries"].append("reactive state")
    assert prior_query_page_ends(tmp_path, plan) == {
        "state management": 6,
        "reactive state": 0,
    }


def test_search_cursor_ignores_different_signature(tmp_path: Path):
    directory = tmp_path / "artifacts" / "self_improvement"
    directory.mkdir(parents=True)
    report = {
        "plan": {
            "failure_class": "side_effectful_target",
            "portable_signature": "side_effectful_target|network|void_side_effect",
            "maximum_search_pages": 2,
            "queries": ["state management"],
        },
        "discovery_rounds": [{"round": 3}],
    }
    (directory / "hypothesis_validation_other.json").write_text(
        json.dumps(report), encoding="utf-8"
    )
    plan = {
        "failure_class": "side_effectful_target",
        "portable_signature": "side_effectful_target|memory_state|void_side_effect",
        "queries": ["state management"],
    }

    assert prior_search_page_end(tmp_path, plan) == 0


def test_round_search_prefers_new_query_and_advances_only_its_cursor():
    plan = {
        "hypothesis_id": "hvp_test",
        "queries": ["old query", "new query"],
        "query_page_cursors": {"old query": 6, "new query": 0},
        "queries_per_round": 1,
        "maximum_search_pages": 2,
    }

    round_plan = build_round_search_plan(plan, 1, set())
    advance_query_cursors(plan, round_plan)

    assert round_plan["queries"] == ["new query"]
    assert round_plan["search_page_start"] == 1
    assert plan["query_page_cursors"] == {"old query": 6, "new query": 2}
