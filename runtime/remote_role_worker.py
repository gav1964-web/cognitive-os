"""Fresh-process role continuation behind the file-message supervisor.

Reproduction is offline: reaching the next unpaid Programmer request after
revalidating immutable roles/tests proves admission, not completion of the task.
"""
import json
import os
import subprocess
import sys
import uuid
from dataclasses import replace
from pathlib import Path

from .remote_role_job import verify_job, ledger_usage, continuation_ledger, save_ledger_pointer, load_known_calls
from .remote_support_protocol import digest, load, save


class AdmissionProbe:
    def __init__(self):
        self.calls = []

    def __call__(self, messages, *, config):
        self.calls.append(config.provider_label)
        raise ValueError('remote_role_next_inference_boundary')


def run_continuation(job, work, chat, configs):
    from .feature_quality import run_quality_development
    return run_quality_development(project=job['project'], work=work, goal=job['goal'],
        python=Path(job['python']), chat=chat, configs=configs,
        resume_roles=job['checkpoint'], challenges=False, max_cycles=1)


def offline_probe(job, work, configs):
    probe = AdmissionProbe()
    result = run_continuation(job, work, probe, configs)
    retained = False
    if result['cycles']:
        report = load(Path(result['cycles'][-1]['checkpoint']) / 'report.json')
        retained = (report.get('frozen_test_hashes') == job['frozen_tests']
            and all(digest(report['artifacts'].get(r)) == h for r, h in job['roles'].items()))
    passed = probe.calls == ['feature:programmer'] and retained and result.get('source_unchanged')
    return {'passed': passed, 'status': 'admitted_to_programmer' if passed else 'blocked',
            'reason': result.get('reason'), 'calls': probe.calls, 'retained': retained,
            'model_calls': 0, 'quality_report': str(work / 'report.json')}


def run_worker(context):
    from .role_inference import role_model_config
    job = verify_job(context)
    configs = {r: replace(role_model_config(r), model=job['model'], fallbacks=(),
        timeout_seconds=240, max_output_tokens=32768) for r in ('analyzer', 'architect', 'spec_writer')}
    phase = context['phase']
    work = Path(job['state_dir']) / ('attempt-' + uuid.uuid4().hex)
    work.mkdir(parents=True)
    admission = offline_probe(job, work / 'admission', configs)
    if phase == 'reproduce' or not admission['passed']:
        return admission
    if phase == 'regression':
        return {**admission, 'reason': 'same-goal-source-role-and-test-bindings-revalidated'}
    if phase != 'resume':
        raise ValueError('remote_role_unknown_phase')
    if context['budget'].get('accounting') != 'role_ledger.v1':
        raise ValueError('remote_role_requires_controller_accounting')
    from .llm_gateway_bootstrap import ensure_llm_gateway_for_url
    from .feature_inference import FeatureChat
    gateway = ensure_llm_gateway_for_url(Path(job['bootstrap_root']), configs['analyzer'].base_url)
    save(work / 'gateway.json', gateway)
    if gateway['status'] not in ('started', 'already_running'):
        raise ValueError('remote_role_gateway_not_ready')
    carry = continuation_ledger(job)
    before = ledger_usage(carry)
    if before['unknown_reserved']:
        raise ValueError('remote_role_prior_usage_unknown')
    remaining = context['budget']['remaining_tokens']
    limit = min(job['budget_limit'], before['reported'] + remaining)
    calls_used = len(load(carry)['jobs'])
    if calls_used >= job['max_calls']:
        raise ValueError('remote_role_series_call_limit')
    out = work / 'live'
    out.mkdir()
    chat = FeatureChat(out, max_calls=job['max_calls'] - calls_used, max_input_bytes=job['max_input_bytes'],
                       carry=carry, budget_limit=limit, known_calls=load_known_calls(job))
    save_ledger_pointer(job, chat.ledger)  # Persist before any paid attempt.
    result = None
    try:
        result = run_continuation(job, work / 'run', chat, configs)
    finally:
        after = ledger_usage(chat.ledger)
        usage = {k: max(0, after[k] - before[k]) for k in before}
        save(Path(os.environ['COS_SUPPORT_RESULT']), {'status': 'incomplete', 'passed': False,
            'usage': usage, 'ledger': str(chat.ledger), 'job_digest': digest(job)})
    native = None
    if result.get('status') == 'verified' and result.get('goal_complete'):
        from .feature_delivery import deliver_feature
        candidate = work / 'delivery'
        delivered = deliver_feature(project=job['project'], checkpoints=[result['checkpoint']],
                                    work=candidate, python=Path(job['python']))
        if delivered['status'] != 'verified':
            raise ValueError('remote_role_delivery_verification_failed')
        target = candidate / 'project'
        argv = [str(target) if a == '{candidate}' else a for a in job['acceptance']['argv']]
        completed = subprocess.run(argv, capture_output=True, text=True, encoding='utf-8',
                                   errors='replace', timeout=60)
        native = {'returncode': completed.returncode, 'output': completed.stdout[-12000:],
                  'stderr': completed.stderr[-2000:], 'delivery': delivered}
    verify_job(context)
    passed = bool(native and native['returncode'] == 0)
    return {'passed': passed, 'status': 'completed' if passed else 'blocked',
        'reason': result.get('reason'), 'usage': usage, 'ledger': str(chat.ledger),
        'model_calls': len(chat.attempts), 'quality_report': str(work / 'run/report.json'),
        'roles': list(load(Path(result['checkpoint']) / 'report.json')['artifacts']) if result.get('checkpoint') else [],
        'native': native, 'job_digest': digest(job)}


def main():
    context = load(os.environ['COS_SUPPORT_CONTEXT'])
    try:
        result = run_worker(context)
    except Exception as exc:
        path = Path(os.environ['COS_SUPPORT_RESULT'])
        result = load(path) if path.exists() else {}
        result.update(passed=False, status='blocked', reason=str(exc))
    save(Path(os.environ['COS_SUPPORT_RESULT']), result)
    print(('COS_ROLE_COMPLETED:' if result['passed'] else 'COS_ROLE_BLOCKED:') + str(result.get('reason')))
    print(json.dumps(result, ensure_ascii=True))
    return 0 if result['passed'] else 1
