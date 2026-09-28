from __future__ import annotations

from copy import deepcopy

import pytest

from runtime.interpreter_authority import (
    InterpreterAuthorityError,
    build_interpreter_decision,
    load_interpreter_authority_policy,
    verify_interpreter_decision,
)


EVIDENCE = [{
    "reference": "report.json",
    "content_digest": "sha256:" + "a" * 64,
    "kind": "project_report",
}]


def _decision(**overrides):
    values = {
        "stage": "project_analysis",
        "goal": "Improve parser",
        "target": "src/parser.py:parse",
        "scope": ["src/parser.py"],
        "evidence": EVIDENCE,
        "candidates": [
            {"candidate_id": "architecture", "next_stage": "architecture", "reason": "known boundary"},
            {"candidate_id": "research", "next_stage": "research", "reason": "unresolved contract"},
        ],
        "selected_candidate_id": "architecture",
        "outcome": "accepted",
        "authority_source": "config/interpreter_authority.json",
        "rule_id": "known-project-route",
    }
    values.update(overrides)
    return build_interpreter_decision(**values)


def test_interpreter_trace_is_replayable_and_keeps_alternatives():
    trace = _decision()

    assert trace["status"] == "accepted"
    assert len(trace["alternatives"]) == 2
    assert verify_interpreter_decision(trace)["status"] == "verified"


def test_interpreter_trace_detects_tampering():
    trace = deepcopy(_decision())
    trace["target"] = "src/other.py:easy"

    assert verify_interpreter_decision(trace)["status"] == "invalid"


def test_interpreter_recovery_preserves_goal_target_and_scope():
    prior = _decision()
    returned = _decision(
        stage="architecture",
        prior_trace=prior,
        candidates=[{"candidate_id": "research", "next_stage": "research", "reason": "need contrast"}],
        selected_candidate_id="research",
        outcome="research_more",
    )

    assert returned["status"] == "accepted"
    assert returned["recovery_count"] == 1


def test_interpreter_recovery_blocks_scope_expansion():
    prior = _decision()
    returned = _decision(
        stage="architecture",
        scope=["src/parser.py", "src/unrelated.py"],
        prior_trace=prior,
        candidates=[{"candidate_id": "research", "next_stage": "research", "reason": "need contrast"}],
        selected_candidate_id="research",
        outcome="research_more",
    )

    assert returned["status"] == "controlled_stop"
    assert "scope_expanded" in returned["violations"]


def test_interpreter_rejects_raw_or_unlisted_authority():
    with pytest.raises(InterpreterAuthorityError, match="authority"):
        _decision(authority_source="llm/raw-output")


def test_web_ui_is_explicitly_deferred():
    policy = load_interpreter_authority_policy()

    assert policy["product_surface"]["web_ui"] == "deferred_until_stable_architecture"
    assert policy["product_surface"]["web_ui_is_current_milestone"] is False
