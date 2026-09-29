"""Real subprocess recovery of a seeded defect in an actual COS module."""
import copy
import json
import sys
import time
from pathlib import Path

import pytest

from runtime.remote_support_protocol import digest, envelope, load, publish, save, verify
from runtime.remote_support_supervisor import SupportSupervisor

KEY = b'test-only-support-channel-key-0001'
ROOT = Path(__file__).resolve().parents[2]
MODULE = 'runtime/feature_read_response.py'
CHECK = '''import json, sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime.feature_read_response import duplicated_read
context = json.loads(Path(os.environ["COS_SUPPORT_CONTEXT"]).read_text(encoding="utf-8"))
assert context["checkpoint"]["sequence"] == 7
assert context["checkpoint"]["role"] == "spec_writer"
row = {"status": "read", "reads": [{"path": "runtime/example.py"}]}
text = json.dumps(row)
assert duplicated_read(text + text) == row, "support_reproduction: duplicated read lost"
if sys.argv[-1] == "regression":
    assert duplicated_read(text) is None
    other = json.dumps({"status": "approve", "reads": row["reads"]})
    assert duplicated_read(other + other) is None
    assert duplicated_read(text + text + "extra") is None
    assert duplicated_read(text + text.replace("example", "different")) is None
print(json.dumps({"status": "completed", "recovered": row, "checkpoint": context["checkpoint"]}))
'''


@pytest.fixture
def setup_support(tmp_path):
    def create(**updates):
        source = tmp_path / 'source'
        (source / 'runtime').mkdir(parents=True)
        (source / 'tests').mkdir()
        (source / 'runtime/__init__.py').write_text('', encoding='utf-8')
        original = (ROOT / MODULE).read_text(encoding='utf-8')
        (source / MODULE).write_text(original.replace('len(content) > 12000', 'len(content) > 12'),
                                     encoding='utf-8')
        (source / 'tests/check.py').write_text(CHECK, encoding='utf-8')
        policy = {'files': ['runtime/__init__.py', MODULE, 'tests/check.py'],
                  'export': [MODULE, 'tests/check.py'], 'editable': [MODULE],
                  'commands': {name: {'argv': [sys.executable, '-B', 'tests/check.py', name],
                                     'timeout': 10} for name in ('reproduce', 'regression', 'resume')},
                  'failure_marker': 'support_reproduction: duplicated read lost',
                  'max_attempts': 3, 'max_messages': 8, 'max_seconds': 60,
                  'expires_at': time.time() + 300, 'max_tokens': 10000,
                  'task': 'Recover a duplicated source read without accepting role decisions',
                  'checkpoint': {'role': 'spec_writer', 'pending': 'source_read', 'sequence': 7},
                  'prior_usage': {'reported': 700, 'unknown_reserved': 30}}
        policy.update(updates)
        supervisor = SupportSupervisor(tmp_path / 'controller', tmp_path / 'to-assistant', KEY)
        request = supervisor.start(source, policy)
        return supervisor, request, source, policy
    return create


def response(request, kind='patch', **changes):
    # The repair author reads ONLY the exported message, never controller/source paths.
    if kind == 'patch':
        payload = {'base': request['payload']['base'], 'reason': 'Restore supported read size',
                   'edits': [{'path': MODULE,
                              'base_sha256': request['payload']['source_hashes'][MODULE],
                              'content': request['payload']['sources'][MODULE].replace(
                                  'len(content) > 12:', 'len(content) > 12000:')}]}
    else:
        payload = {'paths': [MODULE]}
    payload['usage'] = {'reported': 100, 'unknown_reserved': 0}
    payload.update(changes)
    return envelope(kind, request['incident'], payload, KEY, sender='assistant', reply_to=request['id'])


def test_mail_only_repair_fresh_process_resume_and_duplicate(setup_support, tmp_path):
    supervisor, incident, source, policy = setup_support()
    original = (source / MODULE).read_bytes()
    assert incident['kind'] == 'incident'
    assert incident['payload']['failure']['returncode'] == 1
    path = publish(tmp_path / 'to-cos', response(incident))
    result = supervisor.receive(load(path))
    assert result['payload']['status'] == 'completed'
    assert result['payload']['reason'] == 'task_completed_after_repair'
    assert result['payload']['checks']['1-before']['returncode'] == 1
    assert all(result['payload']['checks'][k]['passed'] for k in ('1-reproduce', '1-regression', '1-resume'))
    assert result['payload']['active']['release'] == 'repair-1'
    assert result['payload']['checkpoint_digest'] == digest(policy['checkpoint'])
    assert result['payload']['usage'] == {'reported': 800, 'unknown_reserved': 30, 'prior': policy['prior_usage']}
    assert (source / MODULE).read_bytes() == original  # Only controller-managed releases switch.
    before = (supervisor.home / 'state.json').read_bytes()
    restarted = SupportSupervisor(supervisor.home, supervisor.outbox, KEY)
    assert restarted.receive(load(path)) == result
    assert (supervisor.home / 'state.json').read_bytes() == before


def test_bad_patch_feedback_then_correct_patch(setup_support):
    supervisor, incident, _, _ = setup_support()
    bad = response(incident)
    bad['payload']['edits'][0]['content'] = incident['payload']['sources'][MODULE].replace('> 12:', '> 13:')
    bad = envelope('patch', incident['incident'], bad['payload'], KEY,
                   sender='assistant', reply_to=incident['id'])
    failed = supervisor.receive(bad)
    assert failed['payload']['reason'] == 'support_candidate_reproduce_failed'
    assert failed['payload']['active']['release'] == 'baseline'
    good = response(incident)
    good = envelope('patch', incident['incident'], good['payload'], KEY,
                    sender='assistant', reply_to=failed['id'])
    assert supervisor.receive(good)['payload']['status'] == 'completed'
    assert load(supervisor.home / 'state.json')['tokens'] == 900


@pytest.mark.parametrize('path', ['../secret', 'tests/check.py', 'runtime/remote_support_supervisor.py',
                                   'runtime/x.py:stream', 'C:/temp/file.py'])
def test_patch_cannot_modify_authority_or_escape(setup_support, path):
    supervisor, incident, _, _ = setup_support()
    edit = response(incident)['payload']['edits'][0]
    edit['path'] = path
    result = supervisor.receive(response(incident, edits=[edit]))
    assert result['payload']['reason'] == 'support_edit_scope'
    assert result['payload']['active']['release'] == 'baseline'


def test_context_roundtrip_and_denied_export(setup_support):
    supervisor, incident, _, _ = setup_support()
    context = supervisor.receive(response(incident, 'context_request'))
    assert context['payload']['sources'][MODULE] == incident['payload']['sources'][MODULE]
    denied = supervisor.receive(response(context, 'context_request', paths=['config.json']))
    assert denied['payload']['reason'] == 'support_context_not_authorized'


def test_exported_utf8_bytes_match_bound_source_hash_on_windows(setup_support):
    supervisor, incident, source, _ = setup_support()
    # write_text in the fixture produces CRLF on Windows. Export must not
    # silently normalize those bytes while advertising their original digest.
    exported = incident['payload']['sources'][MODULE].encode('utf-8')
    assert exported == (source / MODULE).read_bytes()
    assert digest(exported) == incident['payload']['source_hashes'][MODULE]
    context = supervisor.receive(response(incident, 'context_request'))
    assert context['payload']['sources'][MODULE].encode('utf-8') == exported


@pytest.mark.parametrize('failure', ['mac', 'incident', 'reply', 'stale'])
def test_binding_rejects_tampering(setup_support, failure):
    supervisor, incident, _, _ = setup_support()
    message = response(incident)
    if failure == 'stale':
        result = supervisor.receive(response(incident, base='wrong'))
        assert result['payload']['reason'] == 'support_stale_patch'
        assert result['payload']['checks'].keys() == {'initial-task'}
        return
    if failure == 'mac':
        message['payload']['edits'][0]['content'] += '\n'
    else:
        message = envelope('patch', '0' * 32 if failure == 'incident' else incident['incident'],
            message['payload'], KEY, sender='assistant', reply_to='0' * 32 if failure == 'reply' else incident['id'])
    with pytest.raises(ValueError):
        supervisor.receive(message)
    assert load(supervisor.home / 'state.json')['attempts'] == 0


def test_regression_catches_overpermissive_fix(setup_support):
    supervisor, incident, _, _ = setup_support()
    content = 'import json\ndef duplicated_read(content):\n    return json.JSONDecoder().raw_decode(content)[0]\n'
    edit = response(incident)['payload']['edits'][0]
    edit['content'] = content
    result = supervisor.receive(response(incident, edits=[edit]))
    assert result['payload']['checks']['1-reproduce']['passed']
    assert result['payload']['reason'] == 'support_candidate_regression_failed'


def test_resume_failure_rolls_back(setup_support):
    supervisor, incident, _, _ = setup_support()
    edit = response(incident)['payload']['edits'][0]
    edit['content'] += '\nimport sys\nif sys.argv[-1] == "resume":\n    raise RuntimeError("resume failed")\n'
    result = supervisor.receive(response(incident, edits=[edit]))
    assert result['payload']['reason'] == 'support_resume_failed'
    assert result['payload']['active']['release'] == 'baseline'


@pytest.mark.parametrize('phase', ['processing', 'activating', 'resuming'])
def test_crash_recovery_never_blindly_repeats_task(setup_support, phase):
    supervisor, _, _, _ = setup_support()
    state = load(supervisor.home / 'state.json')
    state['status'] = phase
    save(supervisor.home / 'state.json', state)
    save(supervisor.home / 'active.json', {'release': 'unconfirmed', 'hashes': {}})
    result = supervisor.recover()
    assert result['payload']['status'] == 'needs_operator'
    assert result['payload']['reason'] == 'interrupted_outcome_unknown'
    assert len(result['payload']['checks']) == 1
    assert result['payload']['active']['release'] == 'baseline'


def test_token_budget_and_prior_usage_survive_recreation(setup_support):
    supervisor, incident, _, policy = setup_support(max_tokens=780)
    result = supervisor.receive(response(incident))
    assert result['payload']['reason'] == 'support_token_limit'
    assert result['payload']['attempts'] == 0
    assert result['payload']['usage']['reported'] == 800  # Preserve prior and newly reported spend.
    assert result['payload']['usage']['prior'] == policy['prior_usage']


def test_attempt_limit(setup_support):
    supervisor, incident, _, _ = setup_support(max_attempts=1)
    result = supervisor.receive(response(incident, base='wrong'))
    assert result['payload']['status'] == 'exhausted'
    assert load(supervisor.home / 'state.json')['attempts'] == 1


def test_local_policy_change_not_accepted(setup_support):
    supervisor, incident, _, _ = setup_support()
    policy = load(supervisor.home / 'policy.json')
    policy['task'] = 'Pretend success'
    save(supervisor.home / 'policy.json', policy)
    with pytest.raises(ValueError, match='policy_changed'):
        supervisor.receive(response(incident))


def test_timeout_is_not_a_reproduced_defect(setup_support):
    commands = {name: {'argv': [sys.executable, '-c', 'import time;time.sleep(5)'], 'timeout': 0.1}
                for name in ('reproduce', 'regression', 'resume')}
    _, incident, _, _ = setup_support(commands=commands)
    assert incident['payload']['status'] == 'needs_operator'
    assert incident['payload']['checks']['initial-task']['timed_out']


def test_message_collision_and_oversize(tmp_path):
    message = envelope('context_request', 'a' * 32, {}, KEY, sender='assistant')
    publish(tmp_path, message)
    changed = copy.deepcopy(message)
    changed['payload']['extra'] = 1
    with pytest.raises(ValueError, match='collision'):
        publish(tmp_path, changed)
    with pytest.raises(ValueError, match='too_large'):
        envelope('patch', 'a' * 32, {'data': 'x' * 2_000_000}, KEY, sender='assistant')


def test_duplicate_json_keys_rejected(tmp_path):
    path = tmp_path / 'bad.json'
    path.write_text('{"payload":{},"payload":{}}')
    with pytest.raises(ValueError, match='duplicate_json_key'):
        load(path)


def test_predeclared_diagnostic_and_unknown_command(setup_support):
    supervisor, incident, _, _ = setup_support()
    context = supervisor.receive(response(incident, 'context_request', paths=[], check='reproduce'))
    assert context['payload']['diagnostic']['returncode'] == 1
    denied = supervisor.receive(response(context, 'context_request', check='shell'))
    assert denied['payload']['reason'] == 'support_diagnostic_not_authorized'


def test_poll_authenticates_and_redelivers_without_execution(setup_support, tmp_path):
    supervisor, incident, _, _ = setup_support()
    incoming = tmp_path / 'incoming'
    message = response(incident)
    publish(incoming, message)
    (incoming / 'malformed.json').write_text('{}')
    report = supervisor.poll(incoming)
    assert len(report['replies']) == 1
    assert len(report['rejected']) == 1
    assert not list(incoming.glob('*.json'))
    assert len(list((incoming / 'processed').glob('*.json'))) == 2
    reply_path = supervisor.outbox / (report['replies'][0] + '.json')
    reply_path.unlink()
    assert supervisor.poll(incoming)['replies'] == []
    assert reply_path.exists()
    assert load(supervisor.home / 'state.json')['attempts'] == 1


def test_message_limit_is_terminal(setup_support):
    supervisor, incident, _, _ = setup_support(max_messages=1)
    context = supervisor.receive(response(incident, 'context_request'))
    result = supervisor.receive(response(context, 'context_request'))
    assert result['payload']['status'] == 'exhausted'
    assert result['payload']['reason'] == 'support_limit'


def test_expired_exchange_never_runs_patch(setup_support, monkeypatch):
    supervisor, incident, _, policy = setup_support()
    monkeypatch.setattr(time, 'time', lambda: policy['expires_at'] + 1)
    result = supervisor.receive(response(incident))
    assert result['payload']['status'] == 'exhausted'
    assert result['payload']['attempts'] == 0


def test_signed_message_id_collision_after_success(setup_support):
    import hashlib
    import hmac
    from runtime.remote_support_protocol import encoded
    supervisor, incident, _, _ = setup_support()
    message = response(incident)
    supervisor.receive(message)
    message['payload']['reason'] = 'changed same ID'
    message['mac'] = hmac.new(KEY, encoded({k: v for k, v in message.items() if k != 'mac'}), hashlib.sha256).hexdigest()
    with pytest.raises(ValueError, match='collision'):
        supervisor.receive(message)


def test_changed_baseline_stops_installation(setup_support):
    supervisor, incident, _, _ = setup_support()
    (supervisor.home / 'releases/baseline' / MODULE).write_text('changed')
    result = supervisor.receive(response(incident))
    assert result['payload']['reason'] == 'support_source_changed'
    assert result['payload']['active']['release'] == 'baseline'


def test_size_gate_before_execution(setup_support):
    supervisor, incident, _, _ = setup_support()
    edit = response(incident)['payload']['edits'][0]
    edit['content'] += '\n# extra\n' * 401
    result = supervisor.receive(response(incident, edits=[edit]))
    assert result['payload']['reason'] == 'support_python_size'
    assert len(result['payload']['checks']) == 1


def test_crashed_check_keeps_time_reservation(setup_support, monkeypatch):
    supervisor, incident, _, _ = setup_support()
    def crash(*args, **kwargs):
        raise SystemExit('controller terminated while child may still run')
    monkeypatch.setattr('runtime.remote_support_supervisor.run_check', crash)
    with pytest.raises(SystemExit):
        supervisor.receive(response(incident))
    result = supervisor.recover()
    assert result['payload']['inflight_check']['reserved_seconds'] == 10
    assert result['payload']['seconds'] >= 10
    assert result['payload']['status'] == 'needs_operator'


def test_context_mutation_cannot_pass_candidate(setup_support):
    supervisor, incident, _, _ = setup_support()
    edit = response(incident)['payload']['edits'][0]
    edit['content'] += '\nimport os\nfrom pathlib import Path\nPath(os.environ["COS_SUPPORT_CONTEXT"]).write_text("{}")\n'
    result = supervisor.receive(response(incident, edits=[edit]))
    assert result['payload']['reason'] == 'support_candidate_reproduce_failed'
    assert result['payload']['checks']['1-reproduce']['context_unchanged'] is False


@pytest.mark.parametrize('path', ['CON.py', 'runtime/../x.py', 'runtime/x.py:secret', '/root/file.py', 'a\\b.py'])
def test_cross_platform_path_rejection(path):
    from runtime.remote_support_protocol import relative_path
    with pytest.raises(ValueError, match='invalid_path'):
        relative_path(path)
