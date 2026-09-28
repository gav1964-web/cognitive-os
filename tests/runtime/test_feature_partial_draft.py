"""Draft reorganization requires comparison by a fresh auditor, never silent acceptance."""
import copy
import json

from runtime.feature_quality_chat import QualityChat
from runtime.local_inference import LocalInferenceConfig
from tests.runtime.test_feature_development import spec
from tests.runtime.test_feature_quality import augment


def test_partial_correction_then_read_retains_complete_draft(tmp_path):
    full = augment('spec_writer', spec())
    partial = copy.deepcopy(full)
    partial['tests'][0]['path'] = 'tests/test_more.py'
    calls, audits = [], []

    def chat(messages, *, config):
        payload = json.loads(messages[1]['content'])
        if config.provider_label == 'quality:spec_auditor':
            audits.append(payload)
            if len(audits) == 2:
                assert payload['previous_unaccepted_draft']['rejected'] == full
                assert payload['omitted_previous_draft_files'] == ['tests/test_labels.py']
            return {'decision': 'reject', 'issues': ['add a boundary']}
        calls.append(payload)
        if len(calls) == 1:
            return full
        if len(calls) == 2:
            return partial
        feedback = payload['quality_contract_feedback']
        assert feedback['rejected'] == full
        assert feedback['incomplete_correction'] == partial
        assert feedback['prior_issues'][0]['acceptance_audit']['issues'] == ['add a boundary']
        assert feedback['issues'][0]['acceptance_audit']['decision'] == 'reject'
        return {'status': 'read', 'reads': [{'path': 'engine.py'}]}

    q = QualityChat(chat, tmp_path)
    payload = {'goal': 'labels', 'artifacts': {'architect': {}}, 'sources': [],
               'source_inventory_digest': 'bound'}
    cfg = LocalInferenceConfig('http://unused', 'fake', provider_label='feature:spec_writer')
    messages = [{'role': 'system', 'content': 'write tests'}, {'role': 'user', 'content': json.dumps(payload)}]
    assert q(messages, config=cfg)['status'] == 'read'
    assert q(messages, config=cfg)['status'] == 'read'
    assert len(audits) == 2
    assert not q.frozen and not q.retained


def test_reorganized_unaccepted_proposal_requires_fresh_audit(tmp_path):
    from runtime.feature_quality_draft import draft_binding
    full = augment('spec_writer', spec())
    reorganized = copy.deepcopy(full)
    reorganized['tests'][0]['path'] = 'tests/test_reorganized.py'
    payload = {'goal': 'labels', 'artifacts': {'architect': {}}, 'sources': []}
    binding = draft_binding(payload, 'spec_writer')
    calls = []

    def chat(messages, *, config):
        assert config.provider_label == 'quality:spec_auditor'
        audit = json.loads(messages[1]['content'])
        calls.append(audit)
        assert audit['previous_unaccepted_draft']['rejected'] == full
        assert audit['specification'] == reorganized
        return {'decision': 'approve'}

    q = QualityChat(chat, tmp_path)
    q.pending['spec_writer'] = {'binding': binding, 'feedback': {'rejected': full, 'issues': ['missing boundary']}}
    q.unaccepted['spec_writer'] = {'binding': binding, 'proposal': reorganized}
    cfg = LocalInferenceConfig('http://unused', 'fake', provider_label='feature:spec_writer')
    result = q([{'role': 'system', 'content': 'spec'},
                {'role': 'user', 'content': json.dumps(payload)}], config=cfg)
    assert result == reorganized and len(calls) == 1
    assert not q.unaccepted and not q.pending and not q.frozen
