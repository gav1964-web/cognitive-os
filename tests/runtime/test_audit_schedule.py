"""Scheduling must not silently approve or erase existing obligations."""
import pytest

from plugins.development_quality.src.audit_schedule import audit_decision
from runtime.feature_quality_chat import QualityChat
from tests.runtime.test_feature_development import project, fake_chat
from tests.runtime.test_feature_quality import augment


@pytest.mark.parametrize('mode', ['always', 'on_feedback'])
@pytest.mark.parametrize('signal', ['feedback', 'scope', 'retained_campaign'])
def test_every_escalation_requires_audit(mode, signal):
    decision = audit_decision(mode, **{signal: ['a.py', 'b.py'] if signal == 'scope' else True})
    assert decision['required'] and not decision['grants_approval']


def test_default_and_experimental_are_distinct():
    assert audit_decision('always')['required']
    assert not audit_decision('on_feedback')['required']
    with pytest.raises(ValueError):
        audit_decision('disabled')


def test_feedback_persists_for_later_audits(tmp_path):
    q = QualityChat(None, tmp_path, audit_mode='on_feedback')
    assert not q.needs_audit('design_auditor', scope=['engine.py'])
    q.record('feedback_routed', owner='spec_writer')
    assert q.needs_audit('spec_auditor')
    assert q.needs_audit('challenger')
    assert all(not e['grants_approval'] for e in q.events if e['event'] == 'audit_schedule')


def test_clean_conditional_cycle_keeps_native_and_reviewer(project, tmp_path):
    import sys
    from pathlib import Path
    from runtime.feature_quality import run_quality_development
    from runtime.local_inference import LocalInferenceConfig
    calls = []
    delegate = fake_chat(project)

    def chat(messages, *, config):
        role = config.provider_label.partition(':')[2]
        calls.append(role)
        assert role not in ('design_auditor', 'spec_auditor', 'challenger')
        return augment(role, delegate(messages, config=config))

    cfg = LocalInferenceConfig('http://unused', 'fake')
    result = run_quality_development(project=project, work=tmp_path/'conditional',
        goal='negative labels', python=Path(sys.executable), chat=chat,
        configs={r: cfg for r in ('analyzer', 'architect', 'spec_writer')}, audit_mode='on_feedback')
    assert result['status'] == 'verified', result
    assert result['source_unchanged'] and result['challenge_status'] == 'not_triggered'
    assert 'programmer' in calls and 'reviewer' in calls
