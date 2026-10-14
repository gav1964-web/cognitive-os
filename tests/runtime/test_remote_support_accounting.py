"""Hard process exits must not turn paid or unknown inference into zero usage."""
import sys
import time
from pathlib import Path

import pytest

from runtime.remote_support_protocol import digest, load, save
from runtime.remote_support_supervisor import SupportSupervisor
from runtime.remote_support_accounting import reserve, reconcile


@pytest.fixture
def accounting(tmp_path):
    initial = tmp_path / 'initial.json'
    save(initial, {'schema_version': 'claim_suite_budget.v1', 'limit_exclusive': 1000000, 'jobs': {
        'prior': {'state': 'done', 'reported_tokens': 100, 'reserved_tokens': 500}}})
    job = {'schema': 'remote_role_job.v1', 'goal': 'test crash',
           'initial_ledger': str(initial), 'initial_ledger_sha256': digest(initial.read_bytes()),
           'state_dir': str(tmp_path / 'worker')}
    save(tmp_path / 'job.json', job)
    policy = {'accounting': 'role_ledger.v1', 'task': job['goal'],
              'checkpoint': {'job_file': str(tmp_path / 'job.json'), 'job_sha256': digest(job)}}
    state = {'tokens': 100, 'unknown_reserved': 0}
    return policy, job, state


def move_ledger(job, rows):
    from runtime.remote_role_job import save_ledger_pointer
    path = Path(job['state_dir']) / 'new/budget.json'
    save(path, {'schema_version': 'claim_suite_budget.v1', 'jobs': rows})
    save_ledger_pointer(job, path)
    return path


@pytest.mark.parametrize('stage,known,unknown', [('ready', 100, 0), ('started', 100, 700), ('done', 321, 0)])
def test_real_worker_hard_exit_reconciles_without_final_json(tmp_path, accounting, stage, known, unknown):
    policy, job, _ = accounting
    source = tmp_path / 'source'
    source.mkdir()
    # A real subprocess dies at a persisted request boundary; no provider is called.
    script = '''import os,json,sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from runtime.remote_support_protocol import load,save
from runtime.remote_role_job import save_ledger_pointer
job=load(sys.argv[2]); stage=sys.argv[3]
rows=load(job['initial_ledger'])['jobs']
rows['new']={'state':stage,'reserved_tokens':700,'reported_tokens':221 if stage=='done' else None}
path=Path(job['state_dir'])/'next/budget.json'
save(path,{'schema_version':'claim_suite_budget.v1','jobs':rows})
save_ledger_pointer(job,path)
os._exit(17)
'''
    (source / 'worker.py').write_text(script)
    argv = [sys.executable, '-B', 'worker.py', str(Path(__file__).resolve().parents[2]),
            policy['checkpoint']['job_file'], stage]
    policy.update(files=['worker.py'], export=['worker.py'], editable=['worker.py'],
        commands={k: {'argv': argv, 'timeout': 10} for k in ('resume', 'regression', 'reproduce')},
        failure_marker='not a repairable failure', max_attempts=1, max_messages=2,
        max_seconds=30, expires_at=time.time()+60, max_tokens=1000,
        prior_usage={'reported':100,'unknown_reserved':0})
    supervisor = SupportSupervisor(tmp_path / 'controller', tmp_path / 'outbox', b'x'*32)
    result = supervisor.start(source, policy)['payload']
    assert result['status'] == 'needs_operator'
    assert result['usage']['reported'] == known
    assert result['usage']['unknown_reserved'] == unknown
    assert result['checks']['initial-task']['accounting']['status'] == 'reconciled'
    again = supervisor.recover()['payload']
    assert again['usage'] == result['usage']


@pytest.mark.parametrize('damage', ['missing', 'truncated', 'lost_history'])
def test_invalid_ledger_retains_entire_allowance(accounting, damage):
    policy, job, state = accounting
    hold = reserve(state, policy, 900)
    path = move_ledger(job, load(job['initial_ledger'])['jobs'])
    if damage == 'missing':
        path.unlink()
    elif damage == 'truncated':
        path.write_text('{')
    else:
        save(path, {'schema_version':'claim_suite_budget.v1','jobs':{}})
    result = {'passed':True,'timed_out':False}
    reconcile(state, policy, hold, result)
    assert not result['passed'] and result['outcome_unknown']
    assert state == {'tokens':100,'unknown_reserved':900}


def test_unknown_ledger_cannot_start_another_process(accounting):
    policy, job, state = accounting
    rows = load(job['initial_ledger'])['jobs']
    rows['pending'] = {'state':'started','reserved_tokens':700,'reported_tokens':None}
    move_ledger(job, rows)
    with pytest.raises(ValueError, match='unknown_requires_reconciliation'):
        reserve(state, policy, 900)


def test_reported_usage_cannot_override_ledger(accounting):
    policy, job, state = accounting
    hold = reserve(state, policy, 900)
    rows = load(job['initial_ledger'])['jobs']
    rows['new'] = {'state':'done','reserved_tokens':700,'reported_tokens':221}
    move_ledger(job, rows)
    result = {'passed':True,'timed_out':False,
              'worker_result':{'usage':{'reported':0,'unknown_reserved':0}}}
    reconcile(state, policy, hold, result)
    assert not result['passed'] and result['accounting_error'] == 'support_worker_usage_mismatch'
    assert state == {'tokens':321,'unknown_reserved':0}


def test_controller_crash_keeps_hold_on_recovery(tmp_path, accounting):
    policy, _, state = accounting
    hold = reserve(state, policy, 900)
    supervisor = SupportSupervisor(tmp_path / 'controller', tmp_path / 'outbox', b'x'*32)
    supervisor.home.mkdir()
    policy['max_tokens'] = 1000
    policy['prior_usage'] = {'reported':100,'unknown_reserved':0}
    save(supervisor.home / 'policy.json', policy)
    state.update(status='resuming', policy_digest=digest(policy), incident='a'*32,
        baseline={}, attempts=1, checks={}, seconds=30, seen={}, task_digest=digest(policy['task']),
        checkpoint_digest=digest(policy['checkpoint']), inflight_check={'accounting':hold})
    save(supervisor.home / 'state.json', state)
    result = supervisor.recover()['payload']
    assert result['status'] == 'needs_operator'
    assert result['usage']['unknown_reserved'] == 900
    assert result['inflight_check']['accounting'] == hold
    with pytest.raises(ValueError,match='termination_confirmation'):
        supervisor.reconcile_interrupted()
    # No worker is alive in this fixture; explicit local confirmation permits accounting only.
    settled = supervisor.reconcile_interrupted(worker_stopped=True)
    assert settled['payload']['status'] == 'needs_operator'
    assert settled['payload']['usage']['unknown_reserved'] == 0
    assert settled['payload']['reason'] == 'interrupted_usage_reconciled_outcome_requires_review'
    assert supervisor.reconcile_interrupted(worker_stopped=True) == settled


def test_exchange_timeout_keeps_hold_while_worker_may_still_run(accounting):
    policy, _, state = accounting
    hold = reserve(state, policy, 900)
    result = {'passed':False,'timed_out':True,'execution_finished':False}
    reconcile(state, policy, hold, result)
    assert state['unknown_reserved'] == 900
    assert result['accounting']['reason'] == 'support_worker_may_still_be_running'


@pytest.mark.parametrize('stage',['started','done'])
def test_actual_feature_chat_persistence_survives_hard_exit(tmp_path, accounting, stage):
    import subprocess
    policy, job, state = accounting
    hold = reserve(state, policy, 99900)
    script = tmp_path/'crash_chat.py'
    script.write_text('''import os,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from runtime.remote_support_protocol import load
from runtime.remote_role_job import save_ledger_pointer
from runtime.feature_inference import FeatureChat
from runtime.local_inference import LocalInferenceConfig
import runtime.claim_suite_budget as budget
job=load(sys.argv[2]); stage=sys.argv[3]
out=Path(job['state_dir'])/'live'; out.mkdir(parents=True)
def transport(messages, *, config):
    config.telemetry_sink({'usage_reported':True,'total_tokens':221})
    return {'ok':True}
chat=FeatureChat(out,carry=job['initial_ledger'],budget_limit=100000,transport=transport)
save_ledger_pointer(job,chat.ledger)
original=budget._write
def persist(path,value):
    original(path,value)
    if any(k!='prior' and r['state']==stage for k,r in value['jobs'].items()):
        os._exit(23)
budget._write=persist
chat([{'role':'user','content':'offline fixture'}],config=LocalInferenceConfig('http://unused','fake',max_output_tokens=32))
''')
    process = subprocess.run([sys.executable,str(script),str(Path(__file__).resolve().parents[2]),
                              policy['checkpoint']['job_file'],stage],capture_output=True,timeout=20)
    assert process.returncode == 23, process.stderr
    result = {'passed':False,'timed_out':False}
    reconcile(state,policy,hold,result)
    assert result['accounting']['status'] == 'reconciled'
    if stage == 'started':
        assert state['tokens'] == 100 and state['unknown_reserved'] > 16384
    else:
        assert state == {'tokens':321,'unknown_reserved':0}


def test_actual_controller_death_preserves_reservation(tmp_path, accounting):
    import subprocess
    policy, _, _ = accounting
    source = tmp_path/'source'
    source.mkdir()
    (source/'subject.py').write_text('pass\n')
    policy.update(files=['subject.py'],export=['subject.py'],editable=['subject.py'],
        commands={k:{'argv':[sys.executable,'subject.py'],'timeout':5} for k in ('resume','reproduce','regression')},
        failure_marker='fixture',max_attempts=1,max_messages=2,max_seconds=20,
        expires_at=time.time()+60,max_tokens=1000,prior_usage={'reported':100,'unknown_reserved':0})
    save(tmp_path/'policy.json',policy)
    script = tmp_path/'crash_controller.py'
    script.write_text('''import os,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from runtime.remote_support_protocol import load
import runtime.remote_support_supervisor as m
base=Path(sys.argv[2])
m.run_check=lambda *args: os._exit(29)
m.SupportSupervisor(base/'controller',base/'outbox',b'x'*32).start(base/'source',load(base/'policy.json'))
''')
    process=subprocess.run([sys.executable,str(script),str(Path(__file__).resolve().parents[2]),str(tmp_path)],
                           capture_output=True,timeout=20)
    assert process.returncode == 29,process.stderr
    supervisor=SupportSupervisor(tmp_path/'controller',tmp_path/'outbox',b'x'*32)
    result=supervisor.recover()['payload']
    assert result['status']=='needs_operator' and result['usage']['unknown_reserved']==900
