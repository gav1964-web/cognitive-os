import json
import sys
from pathlib import Path

import pytest

from runtime.feature_quality import run_quality_development
from runtime.feature_development import run_feature_development
from runtime.feature_progress import repeated_candidate
from runtime.feature_spec_dispute import preservation_outcomes
from runtime.feature_workspace import digest, inventory
from runtime.local_inference import LocalInferenceConfig
from tests.runtime.test_feature_development import project, fake_chat
from tests.runtime.test_feature_quality import augment


def test_identical_candidate_is_detected_despite_new_proposal_wording():
    hashes = {'engine.py': digest(b'wrong'), 'tests/test_x.py': digest(b'test')}
    rows = [{'passed': False, 'candidate_hashes': hashes, 'tests': {'test_x': 'failed'}, 'junit': 'old.xml'}]
    assert repeated_candidate(rows, {'tests/test_x.py': b'test'}, {'engine.py': b'wrong'})
    assert not repeated_candidate(rows, {'tests/test_x.py': b'new test'}, {'engine.py': b'wrong'})
    assert not repeated_candidate(rows, {'tests/test_x.py': b'test'}, {'engine.py': b'corrected'})


@pytest.mark.parametrize('verdict', ['approve', 'reject', 'wrong_digest', 'choose_earlier'])
def test_real_dispute_requires_independent_audit_and_requalifies(project, tmp_path, verdict):
    approve = verdict in ('approve', 'choose_earlier')
    delegate = fake_chat(project)
    called = []
    source_before = inventory(project)

    def chat(messages, *, config):
        role = config.provider_label.partition(':')[2]
        called.append(role)
        payload = json.loads(messages[1]['content'])
        if role in ('design_auditor', 'spec_auditor'):
            return {'decision': 'approve', 'issues': [], 'limitations': []}
        if role == 'spec_dispute_writer':
            assert payload['candidate_failure']['counts']['failed'] == 1
            return {'decision': 'propose_revision', 'candidate_attempt': 1,
                'reason': 'Wrong expected unchanged positive label',
                'goal_quote': 'Preserve positive labels',
                'source_evidence': [{'path': 'engine.py', 'quote': 'return str(value)'}],
                'corrections': [{'path': 'tests/test_labels.py', 'node': 'test_preserve',
                    'old': 'assert display(3) == "003"', 'new': 'assert display(3) == "3"',
                    'reason': 'Original converter returns plain digits'}]}
        if role == 'spec_dispute_auditor':
            assert payload['native_evidence']['candidate']['counts']['failed'] == 0
            return {'decision': 'reject' if verdict == 'reject' else 'approve', 'preserves_goal': verdict != 'reject',
                    'revision_digest': 'wrong' if verdict == 'wrong_digest' else payload['revision_digest'],
                    'reason': 'Independent preservation review'}
        value = augment(role, delegate(messages, config=config))
        if role == 'analyzer':
            return {'status': 'read', 'reads': [{'path': 'engine.py'}]} if called.count(role) == 1 else value
        if role == 'spec_writer':
            value['tests'][0]['content'] += '\ndef test_preserve():\n    assert display(3) == "003"\n'
        if role == 'programmer':
            value['reason'] = 'Conflict: frozen preservation expectation disagrees with original converter'
            if verdict == 'choose_earlier' and called.count(role) == 2:
                value['edits'][0]['replacements'][0]['new'] = 'return "003" if value == 3 else (f"({-value})" if value < 0 else str(value))'
        if role == 'reviewer':
            value['goal_complete'] = True
        return value

    cfg = LocalInferenceConfig('http://unused', 'fake')
    work = tmp_path / 'quality'
    result = run_quality_development(project=project, work=work,
        goal='Parenthesize negatives. Preserve positive labels', python=Path(sys.executable),
        chat=chat, configs={r: cfg for r in ('analyzer', 'architect', 'spec_writer')}, challenges=False)
    assert result['status'] == ('verified' if approve else 'blocked'), result
    assert called.count('spec_dispute_writer') == called.count('spec_dispute_auditor') == 1
    first = json.loads((work / 'cycle-0/report.json').read_text())
    assert len(first['attempts']) == (2 if verdict == 'choose_earlier' else 1)
    assert first['reason'] == ('feature_acceptance_failed' if verdict == 'choose_earlier' else 'feature_candidate_no_progress')
    assert '"003"' in (work / 'cycle-0/spec_writer.json').read_text().replace('\\"', '"')
    if approve:
        assert len(result['spec_revisions']) == 1
        assert called.count('spec_writer') == 1  # Revision is a separate, recorded model proposal.
        assert called.count('spec_auditor') == 2
        final = json.loads((Path(result['checkpoint']) / 'report.json').read_text())
        assert final['attempts'][-1]['passed'] and final['goal_complete']
    else:
        assert result['reason'] == 'quality_spec_dispute_unresolved'
        assert 'reviewer' not in called
    assert inventory(project) == source_before


def test_native_agreement_cannot_hide_removed_or_unrelated_changed_tests():
    correction = [{'path': 'tests/test_x.py', 'node': 'test_preserve'}]
    before = {'new_tests': {'tests': {'tests.test_x::test_preserve': 'failed', 'feature': 'failed'}},
              'regression': {'tests': {'old': 'passed'}}}
    after = {'new_tests': {'tests': {'tests.test_x::test_preserve': 'passed', 'feature': 'passed'}},
             'regression': {'tests': {'old': 'passed'}}}
    with pytest.raises(ValueError, match='unrelated_baseline'):
        preservation_outcomes(before, after, {'tests': before['new_tests']['tests']}, {'passed': True}, correction)
    after['new_tests']['tests'].pop('feature')
    with pytest.raises(ValueError, match='identities'):
        preservation_outcomes(before, after, {'tests': before['new_tests']['tests']}, {'passed': True}, correction)


def test_failed_checkpoint_resumes_real_candidate_and_can_be_corrected(project, tmp_path):
    cfg = LocalInferenceConfig('http://unused', 'fake')
    configs = {r: cfg for r in ('analyzer', 'architect', 'spec_writer')}
    before = run_feature_development(project=project, work=tmp_path / 'initial', goal='negative labels',
        python=Path(sys.executable), chat=fake_chat(project, bad=True), configs=configs)
    assert before['reason'] == 'feature_candidate_no_progress'
    called = []
    delegate = fake_chat(project)
    def chat(messages, *, config):
        called.append(config.provider_label)
        return delegate(messages, config=config)
    result = run_quality_development(project=project, work=tmp_path / 'continued', goal='negative labels',
        python=Path(sys.executable), chat=chat, configs=configs, resume_roles=tmp_path / 'initial', challenges=False)
    assert result['status'] == 'verified', result
    assert called == ['feature:programmer', 'feature:reviewer']
    native = json.loads((Path(result['checkpoint']) / 'report.json').read_text())
    assert [r['passed'] for r in native['attempts']] == [False, True]
