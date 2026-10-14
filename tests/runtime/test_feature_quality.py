import json
import sys
from pathlib import Path

import pytest

from runtime.feature_quality import run_quality_development
from runtime.local_inference import LocalInferenceConfig
from tests.runtime.test_feature_development import project, fake_chat


def augment(role, value):
    if role == 'architect':
        value['states'] = [{'id': str(i), 'when': str(i), 'evidence': 'engine.py',
                            'expected': 'label', 'unknown_behavior': 'preserve'} for i in range(2)]
        value['counterexamples'] = [{'input': i, 'wrong': 'bad', 'expected': 'label', 'because': 'goal'} for i in (1, 2)]
    if role == 'spec_writer':
        value['case_plan'] = [{'kind': k, 'node': 'test_negative', 'behavior': k}
                             for k in ('feature', 'preservation', 'boundary')]
    return value


@pytest.mark.parametrize('owner', ['architect', 'spec_writer', 'programmer'])
def test_reviewer_feedback_is_automatically_routed_without_human(project, tmp_path, owner):
    delegate = fake_chat(project)
    calls, reviews = [], []

    def chat(messages, *, config):
        role = config.provider_label.partition(':')[2]
        calls.append(role)
        if role == 'design_auditor':
            return {'decision': 'approve', 'issues': [], 'limitations': []}
        value = augment(role, delegate(messages, config=config))
        if role == 'reviewer':
            reviews.append(1)
            if len(reviews) == 1:
                value.update(decision='reject', repair_owner=owner, reason='owned defect')
        return value

    cfg = LocalInferenceConfig('http://unused', 'fake')
    report = run_quality_development(project=project, work=tmp_path / 'quality',
        goal='negative labels', python=Path(sys.executable), chat=chat,
        configs={r: cfg for r in ('analyzer', 'architect', 'spec_writer')}, challenges=False)
    assert report['status'] == 'verified', report
    assert report['source_unchanged'] and report['autonomy']['human_interventions'] == 0
    assert len(report['cycles']) == 2
    assert calls.count(owner) >= 2 and calls.count('analyzer') == 1
    journal = json.loads((tmp_path / 'quality/autonomy.json').read_text())
    assert any(e.get('owner') == owner and e.get('phase') == 'cycle' for e in journal['events'])


def test_design_audit_rejection_returns_to_architect(project, tmp_path):
    delegate = fake_chat(project)
    audits = []

    def chat(messages, *, config):
        role = config.provider_label.partition(':')[2]
        if role == 'design_auditor':
            audits.append(1)
            return {'decision': 'reject' if len(audits) == 1 else 'approve',
                    'issues': [{'owner': 'architect', 'reason': 'boundary', 'evidence': 'engine.py'}]}
        return augment(role, delegate(messages, config=config))

    cfg = LocalInferenceConfig('http://unused', 'fake')
    result = run_quality_development(project=project, work=tmp_path / 'quality',
        goal='negative labels', python=Path(sys.executable), chat=chat,
        configs={r: cfg for r in ('analyzer', 'architect', 'spec_writer')}, challenges=False)
    assert result['status'] == 'verified' and len(audits) == 2
    assert result['autonomy']['automatic_routes'] == 1


def test_analyzer_bad_edit_scope_is_repaired_before_architect(project, tmp_path):
    delegate = fake_chat(project)
    analyses = []

    def chat(messages, *, config):
        role = config.provider_label.partition(':')[2]
        if role == 'design_auditor':
            return {'decision': 'approve'}
        value = augment(role, delegate(messages, config=config))
        if role == 'analyzer':
            analyses.append(value)
            if len(analyses) == 1:
                value['scope'].append('tests/test_existing.py')
            else:
                assert json.loads(messages[1]['content'])['quality_contract_feedback']['issues']
        return value

    cfg = LocalInferenceConfig('http://unused', 'fake')
    result = run_quality_development(project=project, work=tmp_path / 'quality',
        goal='negative labels', python=Path(sys.executable), chat=chat,
        configs={r: cfg for r in ('analyzer', 'architect', 'spec_writer')}, challenges=False)
    assert result['status'] == 'verified', result
    assert len(analyses) == 2 and result['autonomy']['automatic_routes'] == 1


def test_acceptance_audit_returns_missing_boundary_to_specwriter(project, tmp_path):
    delegate = fake_chat(project)
    audits = []

    def chat(messages, *, config):
        role = config.provider_label.partition(':')[2]
        if role == 'design_auditor':
            return {'decision': 'approve'}
        if role == 'spec_auditor':
            audits.append(1)
            return {'decision': 'reject' if len(audits) == 1 else 'approve',
                    'issues': [{'owner': 'spec_writer', 'reason': 'missing boundary', 'evidence': 'goal'}]}
        return augment(role, delegate(messages, config=config))

    cfg = LocalInferenceConfig('http://unused', 'fake')
    result = run_quality_development(project=project, work=tmp_path / 'quality',
        goal='negative labels', python=Path(sys.executable), chat=chat,
        configs={r: cfg for r in ('analyzer', 'architect', 'spec_writer')}, challenges=False)
    assert result['status'] == 'verified' and len(audits) == 2
    assert result['autonomy']['automatic_routes'] == 1
