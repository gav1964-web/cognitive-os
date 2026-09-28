"""A model may abstain from a forced edit location without gaining edit authority."""
import json
from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator

from runtime.project_development_llm_hypothesis import (
    _messages, build_llm_failure_hypothesis, enrich_with_llm_failure_hypothesis,
)
from runtime.upstream_llm_candidates import candidate_messages
from tests.runtime.test_project_development_llm_hypothesis import _issue, _project, _config, _payload


def review_payload():
    return {'target': 'module.py:parse_value', 'failure_signature': 'failure-digest',
            'scope_review': {
                'reason': 'The observed API delegates work; the actual corrupting operation is not yet bound.',
                'suspected_targets': ['worker.py:transform'],
                'requested_evidence': ['Trace the result before and after the delegated operation.'],
            }}


def test_alternative_response_does_not_require_a_fictitious_mutation_plan():
    envelope = {'target': 'module.py:parse_value', 'failure_signature': 'failure-digest',
                'reached_returns': [{'id': 'return-1'}]}
    schema = json.loads(_messages(envelope)[0]['content'].split('JSON Schema: ', 1)[1])
    validator = Draft202012Validator(schema)
    validator.validate(review_payload())
    validator.validate({**_payload(), 'reached_return_ids': ['return-1']})
    assert list(validator.iter_errors({**_payload(), **review_payload()}))


def test_scope_review_retains_evidence_without_a_repair_design(tmp_path):
    project = _project(tmp_path)
    calls = []
    def chat(messages, **kwargs):
        envelope = json.loads(messages[1]['content'])
        assert envelope['target_binding_evidence']['root_cause_proven'] is False
        calls.append(messages)
        return review_payload()
    advisory = build_llm_failure_hypothesis(issue=_issue(), project_dir=project, config=_config(), chat=chat)
    assert len(calls) == 1
    assert advisory['status'] == 'scope_review_required'
    assert advisory['scope_review']['authority'] == 'unverified_investigation_hints_only'
    assert advisory['scope_review']['suspected_targets'] == ['worker.py:transform']
    assert advisory['execution_authorized'] is False
    assert 'repair_design' not in advisory and 'causal_hypothesis' not in advisory
    with pytest.raises(ValueError, match='scope_review_required_before_candidates'):
        candidate_messages({'target': advisory['target']}, advisory, '')


@pytest.mark.parametrize('mutation', [
    'target', 'signature', 'authority', 'mixed', 'short_reason', 'oversized_reason',
    'targets_string', 'duplicate_targets', 'many_targets', 'no_evidence', 'nested_patch',
])
def test_invalid_reviews_cannot_change_identity_or_smuggle_a_patch(tmp_path, mutation):
    payload = review_payload()
    review = payload['scope_review']
    if mutation == 'target': payload['target'] = 'other.py:worker'
    elif mutation == 'signature': payload['failure_signature'] = 'other'
    elif mutation == 'authority': payload['execution_authorized'] = True
    elif mutation == 'mixed': payload.update(_payload())
    elif mutation == 'short_reason': review['reason'] = 'unknown'
    elif mutation == 'oversized_reason': review['reason'] = 'x' * 2401
    elif mutation == 'targets_string': review['suspected_targets'] = 'worker.py:transform'
    elif mutation == 'duplicate_targets': review['suspected_targets'] *= 2
    elif mutation == 'many_targets': review['suspected_targets'] = [f'a.py:f{i}' for i in range(5)]
    elif mutation == 'no_evidence': review['requested_evidence'] = []
    elif mutation == 'nested_patch': review['requested_evidence'] = [{'patch': 'code'}]
    result = build_llm_failure_hypothesis(issue=_issue(), project_dir=_project(tmp_path),
                                         config=_config(), chat=lambda *a, **kw: payload)
    assert result['status'] == 'rejected' and result['errors']
    assert 'scope_review' not in result and 'repair_design' not in result


def test_unknown_location_is_valid_and_enrichment_does_not_grant_replay(tmp_path, monkeypatch):
    payload = review_payload()
    payload['scope_review']['suspected_targets'] = []
    monkeypatch.setattr('runtime.project_development_llm_hypothesis.call_json_chat', lambda *a, **kw: payload)
    original = {'issues': [_issue()]}
    before = deepcopy(original)
    result = enrich_with_llm_failure_hypothesis(original, project_dir=_project(tmp_path),
                                               config=_config(), training_replay_authorized=True)
    assert original == before
    issue = result['issues'][0]
    assert issue['llm_hypothesis_advisory']['status'] == 'scope_review_required'
    assert 'causal_hypothesis' not in issue and 'repair_design' not in issue
    assert 'llm_training_replay' not in issue


def test_saved_packet_binding_provenance_reaches_prompt():
    from runtime.project_development_llm_hypothesis import _evidence_envelope
    provenance = {'observed_target': 'api.py:run', 'binding_methods': ['unique_assertion_causal_call'],
                  'authority': 'observed_failure_location_only', 'root_cause_proven': False}
    envelope = _evidence_envelope(target='api.py:run', failure={}, source='def run(): pass',
                                  packet={'target_binding_evidence': provenance})
    assert envelope['target_binding_evidence'] == provenance
    assert envelope['target_binding_evidence'] is not provenance
