"""Keep causal and preservation details intact across role handoffs."""
import json
from copy import deepcopy

import pytest

from runtime.project_development_llm_hypothesis import build_llm_failure_hypothesis
from runtime.project_hypothesis_validation import _validate_payload
from runtime.upstream_llm_candidates import candidate_messages
from tests.runtime.test_project_development_llm_hypothesis import _issue, _project, _config, _payload
from tests.runtime.test_native_failure_acceptance import replay_case
from tests.runtime.test_upstream_llm_trials import _inputs, _hypothesis, _response
from runtime.upstream_llm_trials import validate_llm_diagnosis_proposals


def test_complete_causal_design_and_preservation_reach_candidate(tmp_path):
    payload = _payload()
    payload['mechanism'] = 'Observed cause. ' * 100 + 'CRITICAL_CAUSAL_CONDITION'
    payload['repair_mechanism'] = 'Repair the reached branch. ' * 70 + 'CRITICAL_DESIGN_CONDITION'
    payload['mutation_contract']['preserved_behavior'] = 'Retain other inputs. ' * 60 + 'CRITICAL_PRESERVATION'
    project = _project(tmp_path)
    result = build_llm_failure_hypothesis(issue=_issue(), project_dir=project,
        config=_config(), chat=lambda *args, **kwargs: deepcopy(payload))
    assert result['status'] == 'accepted_hypothesis_only'
    assert result['causal_hypothesis']['mechanism'] == payload['mechanism']
    assert result['repair_design']['mechanism'] == payload['repair_mechanism']
    assert result['repair_design']['mutation_contract'] == payload['mutation_contract']
    messages = candidate_messages({'target': payload['target']}, result,
                                  (project / 'module.py').read_text(encoding='utf-8'))
    envelope = json.loads(messages[1]['content'])
    assert envelope['design']['mutation_contract']['preserved_behavior'].endswith('CRITICAL_PRESERVATION')


@pytest.mark.parametrize('field,value,error', [
    ('mechanism', 'x' * 4001, 'mechanism_budget_exceeded'),
    ('repair_mechanism', ['untrusted text'] * 20, 'repair_mechanism_string_required'),
    ('residual_risks', ['risk'] * 9, 'residual_risks_budget_exceeded'),
    ('residual_risks', ['x' * 1201], 'residual_risks_budget_exceeded'),
])
def test_oversize_or_malformed_contract_is_rejected_not_shortened(field, value, error):
    payload = _payload()
    payload[field] = value
    _, errors = _validate_payload(payload, payload)
    assert error in errors


def test_overlong_preservation_is_rejected():
    payload = _payload()
    payload['mutation_contract']['preserved_behavior'] = 'x' * 2401
    _, errors = _validate_payload(payload, payload)
    assert 'mutation_contract_preserved_behavior_budget_exceeded' in errors


@pytest.mark.parametrize('retry,correct', [(0, True), (1, True), (1, False)])
def test_parser_failure_returns_facts_to_model_only_with_bounded_retry(
        replay_case, tmp_path, retry, correct):
    project, issue = _inputs(replay_case)
    calls = []
    invalid = {'candidates': [{'id': 'bad', 'replacement_source':
        'def close(self):\n    self.pending.clear(\n', 'reason': 'Clear the same list.'}]}
    original = deepcopy(invalid)

    def chat(messages, *, config):
        calls.append(messages)
        if len(calls) == 1:
            return _hypothesis(issue)
        if len(calls) > 2:
            facts = messages[-1]['content']
            assert 'replacement_source_syntax_error' in facts
            assert '"line": 2' in facts and 'parser_error' in facts
            assert 'self.pending.clear(' in facts
            assert json.loads(messages[-2]['content']) == invalid
            return _response() if correct else deepcopy(invalid)
        return deepcopy(invalid)

    result = validate_llm_diagnosis_proposals({'issues': [issue]}, project=project,
        root=tmp_path, config=_config(), chat=chat, authorized=True, format_retries=retry)
    trial = result['issues'][0]['llm_candidate_trial']
    assert len(calls) == 2 + retry
    assert invalid == original
    assert trial['candidate_response_attempts'][0]['validation_error'] == 'replacement_source_syntax_error'
    assert trial['status'] == ('supported_hypothesis_review_required' if retry and correct else 'not_compared')
