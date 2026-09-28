"""One real native comparison after scripted single-function format correction."""
from copy import deepcopy

import pytest

from runtime.local_inference import LocalInferenceConfig
from runtime.model_candidate_feedback import format_feedback
from runtime.upstream_llm_trials import validate_llm_diagnosis_proposals
from tests.runtime.test_native_failure_acceptance import replay_case
from tests.runtime.test_upstream_llm_trials import _inputs, _hypothesis, _response


@pytest.mark.parametrize('correct', [True, False])
def test_module_constant_correction_keeps_design_and_exact_rejected_bytes(tmp_path, replay_case, monkeypatch, correct):
    project, issue = _inputs(replay_case)
    good = {'candidates': [_response()['candidates'][1]]}
    bad = deepcopy(good)
    bad['candidates'][0]['replacement_source'] = 'UNNEEDED = 1\n\n' + good['candidates'][0]['replacement_source']
    prompts = []
    monkeypatch.setattr('runtime.project_development_llm_hypothesis.call_json_chat',
        lambda *a, **kw: _hypothesis(issue))
    def provider(messages, config):
        prompts.append(deepcopy(messages))
        return deepcopy(good if correct and len(prompts) == 2 else bad)
    monkeypatch.setattr('runtime.upstream_llm_trials.call_json_chat', provider)
    result = validate_llm_diagnosis_proposals({'issues': [issue]}, project=project, root=tmp_path,
        config=LocalInferenceConfig(base_url='http://example.invalid', model='scripted'),
        authorized=True, format_retries=1)['issues'][0]
    trial = result['llm_candidate_trial']
    assert trial['logical_model_calls'] == 3
    assert len(prompts) == 2
    assert prompts[1][:2] == prompts[0]
    assert 'Assign' in prompts[1][-1]['content'] and 'FunctionDef' in prompts[1][-1]['content']
    assert 'preserved behavior' in prompts[1][-1]['content']
    assert trial['candidate_response_attempts'][0]['response'] == bad
    assert trial['candidate_response_attempts'][0]['validation_error'] == 'replacement_must_be_single_function'
    assert trial['status'] == ('supported_hypothesis_review_required' if correct else 'not_compared')
    assert trial['delivery_authorized'] is False


def test_feedback_never_truncates_original_prompt_to_fit_budget():
    with pytest.raises(ValueError, match='prompt_budget'):
        format_feedback([{'role': 'user', 'content': 'x' * 72000}], {}, 'candidate_response_schema')
