"""Audited drafts survive read/re-entry but cannot migrate to another design."""
import json

import pytest

from runtime.feature_quality_chat import QualityChat
from runtime.local_inference import LocalInferenceConfig
from tests.runtime.test_feature_development import spec
from tests.runtime.test_feature_quality import augment


@pytest.mark.parametrize('changed', [None, 'goal', 'design', 'source'])
def test_rejected_spec_survives_source_read_until_admission(tmp_path, changed):
    drafts, audits = [], []
    issue = {'owner': 'spec_writer', 'reason': 'missing negative boundary'}

    def chat(messages, *, config):
        payload = json.loads(messages[1]['content'])
        if config.provider_label == 'quality:spec_auditor':
            assert payload['execution_stage'] == 'specification_audit_before_native_qualification'
            audits.append(payload)
            return {'decision': 'reject' if len(audits) == 1 else 'approve',
                    'issues': [issue] if len(audits) == 1 else []}
        drafts.append(payload)
        if len(drafts) == 2:
            assert payload['quality_contract_feedback']['issues']
            return {'status': 'read', 'reads': [{'path': 'engine.py', 'start': 1, 'end': 2}]}
        if len(drafts) == 3:
            assert ('quality_contract_feedback' in payload) is (changed is None)
            if changed is None:
                pending = payload['quality_contract_feedback']
                assert pending['rejected'] == augment('spec_writer', spec())
                assert pending['issues'][0]['acceptance_audit']['issues'] == [issue]
        if len(drafts) == 4:
            assert 'quality_contract_feedback' not in payload
            return {'status': 'read', 'reads': []}
        return augment('spec_writer', spec())

    q = QualityChat(chat, tmp_path)
    cfg = LocalInferenceConfig('http://unused', 'fake', provider_label='feature:spec_writer')
    payload = {'goal': 'negative labels', 'sources': [], 'artifacts': {'architect': {'design': 'v1'}}}

    def invoke():
        return q([{'role': 'system', 'content': 'specification'},
                  {'role': 'user', 'content': json.dumps(payload)}], config=cfg)

    assert invoke()['status'] == 'read'
    q.cycle += 1
    payload['sources'] = [{'path': 'engine.py', 'start': 1, 'end': 2,
                           'content': 'def display(value):\n    return str(value)\n'}]
    if changed == 'goal':
        payload['goal'] = 'other goal'
    if changed == 'design':
        payload['artifacts']['architect']['design'] = 'v2'
    if changed == 'source':
        payload['source_inventory_digest'] = 'different source'
    assert invoke()['status'] == 'ready'
    assert invoke()['status'] == 'read'
    assert not q.pending
