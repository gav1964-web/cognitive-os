"""Repeated code can be referenced, but every byte must remain recoverable."""
from copy import deepcopy
import json

import pytest

from runtime.feature_test_references import compact_test_references, expand_test_references


@pytest.mark.parametrize('field,target', [
    ('immutable_previous_tests', 'quality_contract_feedback'),
    ('specification', 'previous_unaccepted_draft'),
])
def test_roundtrip_keeps_tests_sources_metadata_and_whitespace(field, target):
    test = {'path': 'tests/test_example.py', 'content': '# \u03b1\r\n' * 200 + 'assert x != -1\n'}
    canonical = [test] if field == 'immutable_previous_tests' else {'tests': [test]}
    payload = {field: canonical, target: {'rejected': {'tests': [deepcopy(test)], 'case_plan': ['all']}},
               'sources': [{'path': 'tests/fixture.json', 'content': test['content']}], 'goal': 'keep bytes'}
    before = deepcopy(payload)
    encoded, count = compact_test_references(payload)
    assert count == 1 and expand_test_references(encoded) == before
    assert payload == before and encoded['sources'] == before['sources']
    assert len(json.dumps(encoded)) < len(json.dumps(before))


@pytest.mark.parametrize('change', ['path', 'content', 'ambiguous'])
def test_different_or_ambiguous_versions_are_never_referenced(change):
    test = {'path': 'tests/test_x.py', 'content': '# x\n' * 200}
    other = deepcopy(test)
    frozen = [test]
    if change == 'ambiguous':
        frozen.append({**test, 'content': '# changed\n' * 100})
    else:
        other[change] += 'different'
    payload = {'immutable_previous_tests': frozen,
               'quality_contract_feedback': {'rejected': {'tests': [other]}}}
    encoded, count = compact_test_references(payload)
    assert count == 0 and encoded == payload


def test_missing_canonical_body_cannot_be_decoded():
    test = {'path': 'tests/test_x.py', 'content': '# x\n' * 200}
    payload = {'immutable_previous_tests': [test],
               'quality_contract_feedback': {'rejected': {'tests': [deepcopy(test)]}}}
    encoded, _ = compact_test_references(payload)
    encoded['immutable_previous_tests'] = []
    with pytest.raises(ValueError, match='unresolved'):
        expand_test_references(encoded)


def test_quality_chat_keeps_full_internal_draft_and_audits_literal_output(tmp_path):
    from runtime.feature_quality_chat import QualityChat
    from runtime.feature_quality_draft import draft_binding
    from runtime.local_inference import LocalInferenceConfig
    from tests.runtime.test_feature_development import spec
    from tests.runtime.test_feature_quality import augment
    proposal = augment('spec_writer', spec())
    proposal['tests'][0]['content'] = '# unchanged source\n' * 50 + proposal['tests'][0]['content']
    payload = {'goal': 'labels', 'sources': [], 'artifacts': {'architect': {}}}
    feedback = {'rejected': deepcopy(proposal), 'issues': ['review again']}
    calls = []

    def transport(messages, *, config):
        wire = json.loads(messages[1]['content'])
        assert wire['test_reference_contract']
        expanded = expand_test_references(wire)
        calls.append(config.provider_label)
        if config.provider_label == 'feature:spec_writer':
            assert expanded['quality_contract_feedback'] == feedback
            return deepcopy(proposal)
        assert config.provider_label == 'quality:spec_auditor'
        assert expanded['specification'] == proposal
        assert expanded['previous_unaccepted_draft'] == feedback
        return {'decision': 'approve'}

    q = QualityChat(transport, tmp_path)
    q.frozen = deepcopy(proposal['tests'])
    q.pending['spec_writer'] = {'binding': draft_binding(payload, 'spec_writer'), 'feedback': feedback}
    config = LocalInferenceConfig('http://unused', 'fake', provider_label='feature:spec_writer')
    result = q([{'role': 'system', 'content': 'spec'},
                {'role': 'user', 'content': json.dumps(payload)}], config=config)
    assert result == proposal and feedback['rejected'] == proposal
    assert calls == ['feature:spec_writer', 'quality:spec_auditor']
