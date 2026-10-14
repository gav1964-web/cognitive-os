import sys
from pathlib import Path

import pytest

from runtime.feature_quality import run_quality_development
from runtime.feature_quality_chat import QualityChat
from runtime.feature_quality_routing import reconsider_review_owner
from runtime.local_inference import LocalInferenceConfig
from tests.runtime.test_feature_development import project, fake_chat
from tests.runtime.test_feature_quality import augment


def test_repeated_review_reconsiders_owner_without_approving(tmp_path):
    calls = []
    def chat(messages, *, config):
        calls.append(config.provider_label)
        return {'owner': 'spec_writer', 'reason': 'Requested change is a new test.'}
    q = QualityChat(chat, tmp_path)
    result = {'artifacts': {'reviewer': {'decision': 'reject', 'repair_owner': 'programmer',
              'reason': 'Add an assertion'}}, 'attempts': [{'passed': True}]}
    cfg = LocalInferenceConfig('http://unused', 'fake')
    assert reconsider_review_owner(q, result, cfg, 'programmer') == 'programmer'
    assert not calls
    assert reconsider_review_owner(q, result, cfg, 'programmer') == 'spec_writer'
    assert calls == ['quality:repair_router']
    assert result['artifacts']['reviewer']['decision'] == 'reject'


@pytest.mark.parametrize('require_witness', [False, True])
def test_resume_rejected_review_reuses_patch_and_preserves_native_gates(project, tmp_path, require_witness):
    delegate = fake_chat(project)
    cfg = LocalInferenceConfig('http://unused', 'fake')
    roles = {r: cfg for r in ('analyzer', 'architect', 'spec_writer')}
    def first(messages, *, config):
        role = config.provider_label.partition(':')[2]
        if role in ('design_auditor', 'spec_auditor'):
            return {'decision': 'approve'}
        value = augment(role, delegate(messages, config=config))
        if role == 'reviewer':
            value.update(decision='reject', repair_owner='programmer', reason='missing coverage')
        return value
    old = run_quality_development(project=project, work=tmp_path / 'old/run',
        goal='negative labels', python=Path(sys.executable), chat=first,
        configs=roles, challenges=False, max_cycles=1)
    assert old['status'] == 'blocked'
    calls = []
    def resumed(messages, *, config):
        role = config.provider_label.partition(':')[2]
        calls.append(role)
        if role == 'repair_router':
            return {'owner': 'spec_writer', 'reason': 'Missing acceptance coverage'}
        if role == 'spec_auditor':
            return {'decision': 'approve'}
        return augment(role, delegate(messages, config=config))
    result = run_quality_development(project=project, work=tmp_path / 'new/run',
        goal='negative labels', python=Path(sys.executable), chat=resumed, configs=roles,
        challenges=False, resume_roles=tmp_path / 'old/run/cycle-0', resume_rejected_review=True,
        require_rejected_candidate_witness=require_witness, max_cycles=1)
    if require_witness:
        assert result['status'] == 'blocked'
        assert 'spec_auditor' not in calls and 'reviewer' not in calls
        assert calls.count('spec_writer') == 3
        assert result['source_unchanged']
        return
    assert result['status'] == 'verified', result
    assert result['source_unchanged']
    assert calls == ['repair_router', 'spec_writer', 'spec_auditor', 'reviewer']
