from pathlib import Path

from runtime.spec_writer_ranking_kb import (
    adjustment,
    candidate_kind_adjustment,
    knowledge_leakage_violations,
    load_spec_writer_ranking_kb,
    project_candidate_score,
)


ROOT = Path(__file__).resolve().parents[2]


def test_spec_writer_ranking_kb_is_valid_and_explainable():
    payload = load_spec_writer_ranking_kb()
    score, reason = adjustment("domain.query")

    assert payload["owner_role"] == "spec_writer"
    assert score == 28
    assert "query" in reason


def test_candidate_formulas_are_kb_backed():
    assert candidate_kind_adjustment("bounded_policy")[0] == 55
    assert candidate_kind_adjustment("unknown")[0] == 5
    assert project_candidate_score(500) == 5


def test_decision_modules_have_no_inline_numeric_score_adjustments():
    assert knowledge_leakage_violations(ROOT) == []
