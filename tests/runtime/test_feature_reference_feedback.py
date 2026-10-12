"""Invalid model-authored output references return to Writer, never auto-accept."""
import json
from copy import deepcopy
import pytest

from runtime.feature_quality_chat import QualityChat
from runtime.feature_frozen_references import reference_catalog
from runtime.local_inference import LocalInferenceConfig
from tests.runtime.test_feature_development import spec
from tests.runtime.test_feature_quality import augment


@pytest.mark.parametrize('fixed', [True, False])
def test_stale_output_hash_is_repaired_by_writer_before_any_audit(tmp_path, fixed):
    proposal = augment('spec_writer', spec()); frozen = deepcopy(proposal['tests']); calls = []
    def transport(messages, *, config):
        payload = json.loads(messages[1]['content']); calls.append(config.provider_label)
        if config.provider_label == 'quality:spec_auditor':
            assert fixed and payload['specification']['tests'] == frozen
            return {'decision': 'approve'}
        if len(calls) > 1:
            assert payload['frozen_reference_feedback']['reason'] == 'quality_stale_frozen_reference'
            assert payload['immutable_test_refs'] == reference_catalog(frozen)
        refs = reference_catalog(frozen)
        if len(calls) == 1 or not fixed: refs[0]['content_sha256'] = 'bad hash'
        return {**proposal, 'tests': refs}
    q = QualityChat(transport, tmp_path); q.frozen = frozen
    messages = [{'role': 'system', 'content': 'spec'}, {'role': 'user', 'content': json.dumps({
        'goal': 'labels', 'sources': [], 'artifacts': {'architect': {}}})}]
    config = LocalInferenceConfig('http://unused', 'fake', provider_label='feature:spec_writer')
    if fixed:
        assert q(messages, config=config) == proposal
        assert calls == ['feature:spec_writer', 'feature:spec_writer', 'quality:spec_auditor']
    else:
        with pytest.raises(ValueError, match='quality_role_correction_limit:spec_writer'):
            q(messages, config=config)
        assert calls == ['feature:spec_writer'] * (q.policy['max_format_repairs'] + 1)
    assert q.frozen == frozen and not q.retained


def test_native_rejected_draft_is_distinguished_from_accepted_tests(tmp_path):
    accepted = [{'path': 'tests/test_accepted.py', 'content': 'def test_old(): pass\n'}]
    pending = [{'path': 'tests/test_unaccepted.py', 'content': 'def test_new(): assert False\n'}]
    def transport(messages, *, config):
        payload = json.loads(messages[1]['content'])
        assert payload['specification_authority'] == {
            'immutable_paths': ['tests/test_accepted.py'], 'rejected_drafts_are_accepted': False}
        assert payload['feedback']['rejected_spec']['tests'] == pending
        assert 'remain editable' in messages[0]['content']
        assert payload['immutable_previous_tests'] == accepted
        return {'status': 'blocked', 'reason': 'No automatic approval from authority clarification'}
    q = QualityChat(transport, tmp_path); q.frozen = deepcopy(accepted)
    result = q([{'role': 'system', 'content': 'spec'}, {'role': 'user', 'content': json.dumps({
        'goal': 'labels', 'sources': [], 'artifacts': {'architect': {}},
        'feedback': {'rejected_spec': {'tests': pending}}})}],
        config=LocalInferenceConfig('http://unused', 'fake', provider_label='feature:spec_writer'))
    assert result['status'] == 'blocked' and q.frozen == accepted
