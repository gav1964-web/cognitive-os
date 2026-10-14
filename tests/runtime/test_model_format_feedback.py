"""One explicit format correction preserves rejected answers and all native gates."""
from copy import deepcopy

import pytest

from runtime.local_inference import LocalInferenceConfig
from runtime.upstream_llm_trials import validate_llm_diagnosis_proposals
from tests.runtime.test_native_failure_acceptance import replay_case
from tests.runtime.test_upstream_llm_trials import _inputs, _hypothesis, _response


@pytest.mark.parametrize('budget, repair', [(0, True), (1, True), (1, False)])
def test_bounded_format_feedback_keeps_every_response(tmp_path, replay_case, monkeypatch, budget, repair):
    project, issue = _inputs(replay_case)
    bad = {**_response(), 'schema_version':'unwanted_echo'}
    prompts = []
    monkeypatch.setattr('runtime.project_development_llm_hypothesis.call_json_chat',
        lambda *a, **k: _hypothesis(issue))
    def provider(messages, **kwargs):
        prompts.append(deepcopy(messages))
        return _response() if repair and len(prompts) == 2 else deepcopy(bad)
    monkeypatch.setattr('runtime.upstream_llm_trials.call_json_chat', provider)
    result = validate_llm_diagnosis_proposals({'issues':[issue]},project=project,root=tmp_path,
        config=LocalInferenceConfig(base_url='http://example.test/v1',model='scripted'),authorized=True,format_retries=budget)['issues'][0]
    trial = result['llm_candidate_trial']
    assert trial['logical_model_calls'] == 2 + budget
    assert len(prompts) == 1 + budget
    assert trial['candidate_response_attempts'][0]['response'] == bad
    assert trial['candidate_response_attempts'][0]['validation_error'] == 'candidate_response_schema'
    assert trial['automatic_retry'] is bool(budget)
    if budget:
        assert 'candidate_response_schema' in prompts[-1][-1]['content']
    if budget and repair:
        assert trial['status'] == 'supported_hypothesis_review_required'
    else:
        assert trial['status'] == 'not_compared' and trial['reason'] == 'candidate_response_schema'
    assert trial['delivery_authorized'] is False and result['allowed_operator_ids'] == []


@pytest.mark.parametrize('budget',[True,-1,2])
def test_format_retry_cannot_be_unbounded(tmp_path,budget):
    with pytest.raises(ValueError,match='format_retry_budget'):
        validate_llm_diagnosis_proposals({},project=tmp_path,root=tmp_path,
            config=LocalInferenceConfig(base_url='http://example.test/v1',model='scripted'),authorized=True,format_retries=budget)
