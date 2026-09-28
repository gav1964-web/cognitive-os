"""Lost in-file draft coverage is corrected before another paid audit."""
from copy import deepcopy
import json

from runtime.feature_quality_chat import QualityChat
from runtime.feature_quality_draft import draft_binding
from runtime.local_inference import LocalInferenceConfig
from tests.runtime.test_feature_development import spec
from tests.runtime.test_feature_quality import augment


def test_same_file_partial_draft_is_retained_across_read_and_corrected(tmp_path):
    full = augment('spec_writer', spec())
    full['tests'][0]['content'] += '\ndef test_zero():\n    assert display(0) == "0"\n'
    partial = augment('spec_writer', spec())
    payload = {'goal': 'labels', 'sources': [], 'artifacts': {'architect': {}}}
    calls = []

    def chat(messages, *, config):
        calls.append(config.provider_label)
        value = json.loads(messages[1]['content'])
        if len(calls) == 1:
            assert value['quality_contract_feedback']['rejected'] == full
            assert value['quality_contract_feedback']['incomplete_correction'] == partial
            assert value['quality_contract_feedback']['issues'][0]['draft_case_continuity']['unexplained']
            return {'status': 'read', 'reads': [{'path': 'engine.py'}]}
        if len(calls) == 2:
            assert value['quality_contract_feedback']['rejected'] == full
            return deepcopy(full)
        assert config.provider_label == 'quality:spec_auditor'
        return {'decision': 'approve'}

    q = QualityChat(chat, tmp_path)
    binding = draft_binding(payload, 'spec_writer')
    q.pending['spec_writer'] = {'binding': binding, 'feedback': {'rejected': full, 'issues': ['fix boundary']}}
    q.unaccepted['spec_writer'] = {'binding': binding, 'proposal': partial}
    messages = [{'role': 'system', 'content': 'spec'}, {'role': 'user', 'content': json.dumps(payload)}]
    cfg = LocalInferenceConfig('http://unused', 'fake', provider_label='feature:spec_writer')
    assert q(messages, config=cfg)['status'] == 'read'
    assert q(messages, config=cfg) == full
    assert calls == ['feature:spec_writer', 'feature:spec_writer', 'quality:spec_auditor']
