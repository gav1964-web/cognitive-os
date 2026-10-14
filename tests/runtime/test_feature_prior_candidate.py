"""Paid implementation reuse remains bound to native execution and fresh review."""
import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from runtime.feature_acceptance import save
from runtime.feature_development import run_feature_development
from runtime.feature_quality import run_quality_development
from runtime.local_inference import LocalInferenceConfig
from tests.runtime.test_feature_development import project, fake_chat, run, spec


@pytest.mark.parametrize('tamper', [None, 'proposal', 'design', 'dropped_test'])
def test_reuse_reviewed_candidate_only_with_native_extended_acceptance(project, tmp_path, tamper):
    delegate = fake_chat(project)
    first = run(project, tmp_path, chat=delegate)
    assert first['status'] == 'verified'
    prior = tmp_path / 'run'
    cfg = LocalInferenceConfig('http://unused', 'fake')
    configs = {r: cfg for r in ('analyzer', 'architect', 'spec_writer')}
    expanded = deepcopy(spec())
    expanded['tests'].append({'path': 'tests/test_extra.py', 'content':
        'from engine import display\ndef test_extra():\n    assert display(-3) == "(3)"\n'})
    if tamper == 'dropped_test':
        expanded['tests'] = expanded['tests'][1:]
    qualified = tmp_path / 'qualified'
    stage = run_feature_development(project=project, work=qualified, goal=first['goal'],
        python=Path(sys.executable), chat=lambda *a, **k: expanded, configs=configs,
        resume_roles=prior, fresh_spec=True, stop_after='spec_writer')
    assert stage['status'] == 'spec_qualified'
    if tamper == 'proposal':
        p = prior / 'proposal-1.json'; value = json.loads(p.read_text())
        value['edits'][0]['replacements'][0]['new'] += ' # tampered'
        save(p, value)
    elif tamper == 'design':
        stage['artifacts']['architect']['design'] = 'different design'
        save(qualified / 'report.json', stage)
        save(qualified / 'architect.json', stage['artifacts']['architect'])
    calls = []
    def chat(messages, *, config):
        calls.append(config.provider_label)
        assert config.provider_label == 'feature:reviewer'
        payload = json.loads(messages[1]['content'])
        assert payload['verification']['passed']
        assert len(payload['artifacts']['spec_writer']['tests']) == 2
        return delegate(messages, config=config)
    result = run_quality_development(project=project, work=tmp_path / 'resume', goal=first['goal'],
        python=Path(sys.executable), chat=chat, configs=configs, challenges=False,
        resume_roles=qualified, resume_candidate_from=prior)
    if tamper:
        assert result['status'] == 'blocked' and not calls
        assert any(s in result['reason'] for s in ('candidate_changed', 'same_design', 'test_extension'))
    else:
        assert result['status'] == 'verified', result
        assert calls == ['feature:reviewer']
        assert result['source_unchanged'] and not result['source_apply']


def test_newly_exposed_defect_returns_to_programmer_instead_of_accepting_old_patch(project, tmp_path):
    delegate = fake_chat(project)
    def limited(messages, *, config):
        response = delegate(messages, config=config)
        if config.provider_label == 'feature:programmer':
            response['edits'][0]['replacements'][0]['new'] = 'return "(2)" if value == -2 else str(value)'
        return response
    first = run(project, tmp_path, chat=limited)
    assert first['status'] == 'verified'
    cfg = LocalInferenceConfig('http://unused', 'fake')
    configs = {r: cfg for r in ('analyzer', 'architect', 'spec_writer')}
    expanded = deepcopy(spec())
    expanded['tests'].append({'path': 'tests/test_extra.py', 'content':
        'from engine import display\ndef test_extra():\n    assert display(-3) == "(3)"\n'})
    qualified = tmp_path / 'qualified'
    stage = run_feature_development(project=project, work=qualified, goal=first['goal'],
        python=Path(sys.executable), chat=lambda *a, **k: expanded, configs=configs,
        resume_roles=tmp_path / 'run', fresh_spec=True, stop_after='spec_writer')
    assert stage['status'] == 'spec_qualified'
    calls = []
    def chat(messages, *, config):
        calls.append(config.provider_label)
        if config.provider_label == 'feature:programmer':
            payload = json.loads(messages[1]['content'])
            assert payload['feedback']['verification']['failures']
        return delegate(messages, config=config)
    result = run_feature_development(project=project, work=tmp_path / 'resume', goal=first['goal'],
        python=Path(sys.executable), chat=chat, configs=configs, resume_roles=qualified,
        resume_candidate_from=tmp_path / 'run')
    assert result['status'] == 'verified', result
    assert [r['passed'] for r in result['attempts']] == [False, True]
    assert calls == ['feature:programmer', 'feature:reviewer']


@pytest.mark.parametrize('defect', [None, 'dropped_test', 'wrong_baseline'])
def test_fresh_draft_must_qualify_before_prior_candidate_reuse(project, tmp_path, defect):
    delegate = fake_chat(project)
    first = run(project, tmp_path, chat=delegate)
    assert first['status'] == 'verified'
    proposal = deepcopy(spec())
    proposal['tests'].append({'path': 'tests/test_extra.py', 'content':
        'from engine import display\ndef test_extra():\n    assert display(-3) == "(3)"\n'})
    if defect == 'dropped_test': proposal['tests'] = proposal['tests'][1:]
    if defect == 'wrong_baseline': proposal['tests'][-1]['content'] = 'import missing_test_dependency\n'
    calls = []
    def chat(messages, *, config):
        calls.append(config.provider_label)
        if config.provider_label == 'feature:spec_writer': return proposal
        assert config.provider_label == 'feature:reviewer'
        return delegate(messages, config=config)
    cfg = LocalInferenceConfig('http://unused', 'fake')
    result = run_feature_development(project=project, work=tmp_path/'fresh-reuse', goal=first['goal'],
        python=Path(sys.executable), chat=chat,
        configs={r:cfg for r in ('analyzer','architect','spec_writer')},
        resume_roles=tmp_path/'run', resume_candidate_from=tmp_path/'run', fresh_spec=True)
    if defect:
        assert result['status'] == 'blocked' and 'feature:reviewer' not in calls
        assert not result['attempts']
    else:
        assert result['status'] == 'verified'
        assert calls == ['feature:spec_writer', 'feature:reviewer']
    assert not result['source_apply']
