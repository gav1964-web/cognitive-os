"""Role admission contracts, independent of any live provider or project name."""
import sys
from pathlib import Path

import pytest

from runtime.feature_development import run_feature_development
from runtime.local_inference import LocalInferenceConfig
from runtime.remote_role_job import bind_job, continuation_ledger, ledger_usage, verify_job
from runtime.remote_role_worker import offline_probe
from runtime.remote_support_protocol import digest, load, save
from tests.runtime.test_feature_development import project, fake_chat


@pytest.fixture
def bound_job(project, tmp_path):
    cfg = LocalInferenceConfig('http://unused', 'fake')
    configs = {r: cfg for r in ('analyzer', 'architect', 'spec_writer')}
    checkpoint = tmp_path / 'qualified'
    result = run_feature_development(project=project, work=checkpoint, goal='negative labels',
        python=Path(sys.executable), chat=fake_chat(project), configs=configs, stop_after='spec_writer')
    assert result['status'] == 'spec_qualified'
    ledger = tmp_path / 'budget.json'
    save(ledger, {'jobs': {'test-only-slot': {'state': 'done', 'reported_tokens': 300, 'reserved_tokens': 300}}})
    accept = tmp_path / 'external_check.py'
    accept.write_text('assert True\n', encoding='utf-8')
    job = bind_job(project=project, checkpoint=checkpoint, ledger=ledger, goal='negative labels',
        python=sys.executable, model='fake', state_dir=tmp_path / 'state', budget_limit=900000,
        bootstrap_root=tmp_path, acceptance={'argv': [sys.executable, str(accept), '{candidate}'],
                                           'files': [str(accept)]})
    path = tmp_path / 'job.json'
    save(path, job)
    binding = {'job_file': str(path), 'job_sha256': digest(job)}
    context = {'task': job['goal'], 'task_digest': digest(job['goal']), 'checkpoint': binding,
               'checkpoint_digest': digest(binding), 'phase': 'reproduce'}
    return job, context, configs


def test_qualified_spec_resume_reaches_programmer_without_paid_calls(bound_job, tmp_path):
    job, context, configs = bound_job
    assert verify_job(context) == job
    result = offline_probe(job, tmp_path / 'probe', configs)
    assert result['passed'], result
    assert result['retained'] and result['model_calls'] == 0
    assert result['calls'] == ['feature:programmer']


@pytest.mark.parametrize('what', ['target', 'checkpoint', 'auxiliary', 'goal', 'acceptance', 'ledger'])
def test_changed_bound_evidence_blocks_before_role_execution(bound_job, what):
    job, context, _ = bound_job
    if what == 'target':
        (Path(job['project']) / 'engine.py').write_text('changed')
    elif what == 'checkpoint':
        path = Path(job['checkpoint']) / 'spec_writer.json'
        value = load(path)
        value['tests'][0]['content'] = 'assert True'
        save(path, value)
    elif what == 'auxiliary':
        save(Path(job['checkpoint']).parent / 'transcript.json', [])
    elif what == 'goal':
        context['task'] = 'different'
    elif what == 'acceptance':
        Path(next(iter(job['acceptance']['files']))).write_text('raise Exception()')
    else:
        save(Path(job['initial_ledger']), {'jobs': {}})
    with pytest.raises(ValueError, match='changed'):
        verify_job(context)


def test_ledger_preserves_unknown_and_prior_usage(tmp_path):
    path = tmp_path / 'ledger.json'
    save(path, {'jobs': {'a': {'state': 'done', 'reported_tokens': 120, 'reserved_tokens': 500},
                        'b': {'state': 'started', 'reserved_tokens': 800},
                        'c': {'state': 'unknown', 'reserved_tokens': 900}}})
    assert ledger_usage(path) == {'reported': 120, 'unknown_reserved': 1700}


def test_unrelated_series_cannot_replace_ledger(bound_job):
    job, _, _ = bound_job
    save(Path(job['state_dir']) / 'ledger-pointer.json', {'job_digest': 'different', 'path': job['initial_ledger']})
    with pytest.raises(ValueError, match='series_identity'):
        continuation_ledger(job)


def test_probe_failure_is_not_reported_as_completed(bound_job, tmp_path, monkeypatch):
    job, _, configs = bound_job
    monkeypatch.setattr('runtime.remote_role_worker.run_continuation',
        lambda *args: {'status': 'verified', 'cycles': [], 'source_unchanged': True})
    result = offline_probe(job, tmp_path / 'fake-probe', configs)
    assert not result['passed'] and not result['retained']


def test_unqualified_checkpoint_cannot_be_bound(bound_job, tmp_path):
    job, _, _ = bound_job
    path = Path(job['checkpoint']) / 'report.json'
    report = load(path)
    report['status'] = 'blocked'
    save(path, report)
    with pytest.raises(ValueError, match='current_qualified_spec'):
        bind_job(project=job['project'], checkpoint=job['checkpoint'], ledger=job['initial_ledger'],
            goal=job['goal'], python=sys.executable, model='fake', state_dir=tmp_path / 'another',
            budget_limit=900000, acceptance=job['acceptance'], bootstrap_root=tmp_path)


@pytest.mark.parametrize('change', ['status', 'attempt', 'accepted_test'])
def test_resume_cannot_promote_other_boundaries(bound_job, tmp_path, change):
    job, _, configs = bound_job
    path = Path(job['checkpoint']) / 'report.json'
    report = load(path)
    if change == 'status':
        report['status'] = 'verified'
    elif change == 'attempt':
        report['attempts'] = [{'passed': True}]
    else:
        report['artifacts']['spec_writer']['tests'][0]['content'] = 'assert True'
    save(path, report)
    result = offline_probe(job, tmp_path / 'rejected-probe', configs)
    assert not result['passed']
    assert result['calls'] == []
    expected_reason = {
        'status': 'quality_resume_requires_qualified_spec_boundary',
        'attempt': 'quality_resume_requires_pending_candidate_review',
        'accepted_test': 'feature_checkpoint_frozen_spec_mismatch',
    }
    assert result['reason'] == expected_reason[change]


def test_live_worker_requires_controller_accounting(bound_job, monkeypatch):
    from runtime.remote_role_worker import run_worker
    job, context, _ = bound_job
    context.update(phase='resume',budget={'remaining_tokens':900000})
    monkeypatch.setattr('runtime.remote_role_worker.offline_probe',lambda *args:{'passed':True})
    with pytest.raises(ValueError,match='requires_controller_accounting'):
        run_worker(context)


def test_live_worker_passes_pinned_history_for_accounting_only(bound_job, tmp_path, monkeypatch):
    from runtime.remote_role_worker import run_worker
    from runtime.narrow_type_evidence_binding import content_digest
    job, context, _ = bound_job
    calls = tmp_path / 'known-calls.json'
    rows = [{'messages': [], 'request_digest': content_digest([])}]
    save(calls, rows)
    job['known_calls'] = {str(calls): digest(calls.read_bytes())}
    save(context['checkpoint']['job_file'], job)
    context['checkpoint']['job_sha256'] = digest(job)
    context['checkpoint_digest'] = digest(context['checkpoint'])
    context.update(phase='resume', budget={'accounting': 'role_ledger.v1', 'remaining_tokens': 899700})
    monkeypatch.setattr('runtime.remote_role_worker.offline_probe', lambda *args: {'passed': True})
    monkeypatch.setattr('runtime.llm_gateway_bootstrap.ensure_llm_gateway_for_url',
                        lambda *args: {'status': 'already_running'})

    def capture(output, **kwargs):
        assert kwargs['known_calls'] == rows
        assert 'previous' not in kwargs
        assert kwargs['carry'] == Path(job['initial_ledger'])
        raise RuntimeError('verified_accounting_boundary')

    monkeypatch.setattr('runtime.feature_inference.FeatureChat', capture)
    with pytest.raises(RuntimeError, match='verified_accounting_boundary'):
        run_worker(context)
    save(calls, [])
    with pytest.raises(ValueError, match='known_calls_changed'):
        verify_job(context)
