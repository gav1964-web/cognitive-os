"""Immutable selected releases and a local-policy subprocess adapter.

This runner is for authenticated, trusted repairs, not hostile code isolation.
Deploy it under OS isolation/ACLs when the worker must not reach its supervisor.
"""
import ast
import os
import subprocess
import time
from pathlib import Path

from .remote_support_protocol import digest, owned, relative_path, save, encoded, load


def inventory(root, names):
    return {name: digest(owned(root, name).read_bytes()) for name in sorted(names)}


def snapshot(source, destination, expected):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    for name, wanted in expected.items():
        data = owned(source, name).read_bytes()
        if digest(data) != wanted:
            raise ValueError('support_source_changed')
        path = owned(destination, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return destination


def validate_policy(policy):
    required = {'files', 'export', 'editable', 'commands', 'failure_marker',
                'max_attempts', 'max_messages', 'max_seconds', 'expires_at',
                'max_tokens', 'task', 'checkpoint', 'prior_usage'}
    if set(policy) - {'accounting', 'execution'} != required:
        raise ValueError('support_policy_fields')
    from .remote_support_accounting import validate_accounting
    validate_accounting(policy)
    from .remote_support_exchange import validate_execution
    validate_execution(policy.get('execution'))
    files = policy['files']
    if not files or len(files) > 3000 or len({n.lower() for n in files}) != len(files):
        raise ValueError('support_policy_files')
    for name in files:
        relative_path(name)
        if Path(name).name.lower() == 'config.json' or any(
                word in name.lower() for word in ('secret', 'credential', '.env')):
            raise ValueError('support_private_file')
    if not set(policy['export']) <= set(files) or not set(policy['editable']) <= set(files):
        raise ValueError('support_policy_scope')
    for name in policy['editable']:
        if (not name.endswith('.py') or name.startswith('tests/')
                or 'remote_support' in name):
            raise ValueError('support_protected_file')
    if not policy['editable'] or not policy['failure_marker'] or not policy['task']:
        raise ValueError('support_policy_empty')
    for name in ('max_attempts', 'max_messages', 'max_seconds', 'max_tokens'):
        if type(policy[name]) is not int or policy[name] < 1:
            raise ValueError('support_policy_limit')
    if policy['max_attempts'] > 10 or policy['max_messages'] > 32:
        raise ValueError('support_policy_limit')
    usage = policy['prior_usage']
    if (not isinstance(usage, dict) or set(usage) != {'reported', 'unknown_reserved'}
            or any(type(v) is not int or v < 0 for v in usage.values())):
        raise ValueError('support_prior_usage')
    if not isinstance(policy['expires_at'], (int, float)) or policy['expires_at'] <= time.time():
        raise ValueError('support_policy_expired')
    commands = policy['commands']
    if set(commands) != {'reproduce', 'regression', 'resume'}:
        raise ValueError('support_policy_commands')
    for command in commands.values():
        if (set(command) != {'argv', 'timeout'} or not command['argv']
                or not all(isinstance(v, str) and v for v in command['argv'])
                or not Path(command['argv'][0]).is_absolute()
                or not 0 < command['timeout'] <= policy['max_seconds']):
            raise ValueError('support_policy_command')


def apply_patch(root, expected, payload, policy):
    if payload.get('base') != digest(expected):
        raise ValueError('support_stale_patch')
    edits = payload.get('edits')
    if not isinstance(edits, list) or not edits:
        raise ValueError('support_empty_patch')
    prepared = {}
    for edit in edits:
        name = edit['path']
        if name not in policy['editable'] or name in prepared:
            raise ValueError('support_edit_scope')
        if edit.get('base_sha256') != expected.get(name):
            raise ValueError('support_stale_patch')
        content = edit['content']
        if not isinstance(content, str) or len(content.encode('utf-8')) > 120000:
            raise ValueError('support_edit_size')
        if len(content.splitlines()) > 400:
            raise ValueError('support_python_size')
        ast.parse(content)
        prepared[name] = content.encode('utf-8')
    if all(digest(value) == expected[name] for name, value in prepared.items()):
        raise ValueError('support_no_change')
    for name, value in prepared.items():
        owned(root, name).write_bytes(value)
    return inventory(root, expected)


def run_check(root, command, output, expected, remaining, context, *, stop_requested=None):
    """Run only a locally frozen argv. Never accept commands from a message."""
    if context.get('execution'):
        from .remote_support_exchange import dispatch
        return dispatch(root, command, output, expected, remaining, context, context['execution'])
    timeout = min(command['timeout'], remaining)
    if timeout <= 0:
        raise ValueError('support_time_budget')
    if stop_requested and stop_requested():
        raise ValueError('support_worker_stopping')
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    context_path = output.with_suffix('.context.json')
    result_path = output.with_suffix('.result.json')
    if result_path.exists():
        raise ValueError('support_worker_result_already_exists')
    save(context_path, context)
    env = {k: v for k, v in os.environ.items() if k.upper() in {
        'SYSTEMROOT', 'WINDIR', 'PATH', 'TEMP', 'TMP', 'LANG', 'LC_ALL', 'HOME', 'USERPROFILE'}}
    env.update(PYTHONDONTWRITEBYTECODE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
               PYTHONIOENCODING='utf-8', COS_SUPPORT_CONTEXT=str(context_path.resolve()),
               COS_SUPPORT_RESULT=str(result_path.resolve()))
    started = time.monotonic()
    with output.open('wb') as stream:
        process = subprocess.Popen(command['argv'], cwd=root, env=env, shell=False,
            stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            start_new_session=os.name != 'nt')
        timed_out = False
        cancelled = False
        try:
            if stop_requested is None:
                process.wait(timeout=timeout)
            else:
                while process.poll() is None:
                    cancelled = stop_requested()
                    left = timeout - (time.monotonic() - started)
                    if cancelled or left <= 0:
                        raise subprocess.TimeoutExpired(command['argv'], timeout)
                    try:
                        process.wait(timeout=min(0.2, left))
                    except subprocess.TimeoutExpired:
                        continue
        except subprocess.TimeoutExpired:
            timed_out = not cancelled
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                    capture_output=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                import signal
                os.killpg(process.pid, signal.SIGKILL)
            process.kill()
            process.wait(timeout=10)
    with output.open('rb') as stream:
        raw = stream.read(16001)
    unchanged = inventory(root, expected) == expected
    context_unchanged = context_path.read_bytes() == encoded(context)
    worker_result = load(result_path) if result_path.exists() else None
    if worker_result is not None and not isinstance(worker_result, dict):
        raise ValueError('support_worker_result_invalid')
    return {'returncode': process.returncode, 'timed_out': timed_out, 'cancelled': cancelled,
            'seconds': round(time.monotonic() - started, 3), 'source_unchanged': unchanged,
            'context_unchanged': context_unchanged,
            'worker_result': worker_result,
            'output': raw[:16000].decode('utf-8', errors='replace'),
            'output_truncated': len(raw) > 16000,
            'passed': process.returncode == 0 and not timed_out and not cancelled and unchanged and context_unchanged
                      and (worker_result is None or worker_result.get('passed') is True)}
