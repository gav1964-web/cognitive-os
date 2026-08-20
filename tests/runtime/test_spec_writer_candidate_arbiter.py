from unittest.mock import patch

from runtime.local_inference import LocalInferenceConfig, LocalInferenceError
from runtime.spec_writer_candidate_arbiter import _needs_arbitration, arbitrate_candidates


def _config() -> LocalInferenceConfig:
    return LocalInferenceConfig(base_url="http://local", model="test", provider_label="test")


def test_arbiter_only_runs_for_close_weak_candidates():
    assert _needs_arbitration([{"score": 90, "semantic_score": 84}, {"score": 82, "semantic_score": 96}])
    assert not _needs_arbitration([{"score": 100, "semantic_score": 98}, {"score": 99, "semantic_score": 96}])
    assert not _needs_arbitration([{"score": 100, "semantic_score": 84}, {"score": 70, "semantic_score": 96}])


def test_arbiter_can_only_select_existing_top_n_source():
    ranked = [
        {"source": "signals.py:on_done", "score": 90, "semantic_score": 84, "reasons": [], "evidence": {}},
        {"source": "policy.py:validate", "score": 84, "semantic_score": 96, "reasons": [], "evidence": {}},
    ]
    with patch(
        "runtime.spec_writer_candidate_arbiter.call_json_chat",
        return_value={"selected_source": "policy.py:validate", "reason": "bounded deterministic validator"},
    ):
        result, advisory = arbitrate_candidates(ranked, config=_config())

    assert result[0]["source"] == "policy.py:validate"
    assert advisory["llm_invoked"] is True
    assert advisory["accepted"] is True


def test_arbiter_rejects_invented_source():
    ranked = [
        {"source": "a.py:first", "score": 90, "semantic_score": 84, "reasons": [], "evidence": {}},
        {"source": "b.py:second", "score": 84, "semantic_score": 90, "reasons": [], "evidence": {}},
    ]
    with patch(
        "runtime.spec_writer_candidate_arbiter.call_json_chat",
        return_value={"selected_source": "invented.py:target"},
    ):
        result, advisory = arbitrate_candidates(ranked, config=_config())

    assert result[0]["source"] == "a.py:first"
    assert advisory["accepted"] is False


def test_arbiter_retries_once_with_compact_evidence():
    ranked = [
        {"source": "a.py:first", "score": 90, "semantic_score": 84, "reasons": [], "evidence": {}},
        {"source": "b.py:second", "score": 84, "semantic_score": 90, "reasons": [], "evidence": {}},
    ]
    with patch(
        "runtime.spec_writer_candidate_arbiter.call_json_chat",
        side_effect=[LocalInferenceError("too long"), {"selected_source": "b.py:second", "reason": "bounded"}],
    ) as mocked:
        result, advisory = arbitrate_candidates(ranked, config=_config())

    assert mocked.call_count == 2
    assert result[0]["source"] == "b.py:second"
    assert advisory["accepted"] is True


def test_self_improvement_challenger_selects_exact_bounded_source_without_llm():
    ranked = [
        {"source": "signals.py:on_done", "score": 90, "semantic_score": 84, "reasons": [], "evidence": {}},
        {"source": "service.py:sync", "score": 84, "semantic_score": 92, "reasons": [], "evidence": {}},
    ]
    config = LocalInferenceConfig(
        base_url="http://local",
        model="test",
        advisory_context={"preferred_source": "service.py:sync"},
    )

    result, advisory = arbitrate_candidates(ranked, config=config)

    assert result[0]["source"] == "service.py:sync"
    assert advisory["source"] == "self_improvement_challenger"
    assert advisory["llm_invoked"] is False


def test_self_improvement_challenger_can_reach_beyond_normal_top_five():
    ranked = [
        {"source": f"service.py:candidate_{index}", "score": 100 - index, "reasons": [], "evidence": {}}
        for index in range(8)
    ]
    config = LocalInferenceConfig(
        base_url="http://local",
        model="test",
        advisory_context={"preferred_source": "service.py:candidate_6"},
    )

    result, advisory = arbitrate_candidates(ranked, config=config)

    assert result[0]["source"] == "service.py:candidate_6"
    assert advisory["source"] == "self_improvement_challenger"
    assert advisory["llm_invoked"] is False
