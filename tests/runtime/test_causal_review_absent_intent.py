"""Blocked plans may omit intent; model delivery still requires comparison."""
import pytest

from runtime.upstream_causal_review import causal_comparison_checks


@pytest.mark.parametrize('spec', [{}, {'implementation_delta':None},
                                  {'implementation_delta':{}}, {'implementation_delta':{'intent':None}}])
def test_absent_intent_has_no_causal_delivery_claim(spec):
    assert causal_comparison_checks(spec, {}) == []


@pytest.mark.parametrize('intent', [{'model_delivery':{}}, {'authority':'explicit_model_candidate_replay'}])
def test_model_delivery_without_comparison_still_fails(intent):
    rows = causal_comparison_checks({'implementation_delta':{'intent':intent}}, {})
    assert len(rows) == 1
    assert rows[0]['passed'] is False
