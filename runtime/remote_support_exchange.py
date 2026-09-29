"""Local file jobs executed by an independently launched worker identity.

Request directories are controller-owned; the worker may modify only source and
output copies. The controller never exposes its home, policy or signing key.
The worker executes trusted local policy commands, not commands from mail.
"""
import time
import uuid
from pathlib import Path

from .remote_support_protocol import digest, load, save, owned


def validate_execution(value):
    if value is None:
        return
    from .remote_support_windows import sid
    if (not isinstance(value, dict) or set(value) != {'kind','root','controller_sid','worker_sid'}
            or value['kind'] != 'windows_file_worker.v1'
            or not Path(value['root']).is_absolute()
            or value['controller_sid'] == value['worker_sid']):
        raise ValueError('support_execution_contract')
    sid(value['controller_sid'])
    sid(value['worker_sid'])


def validate_location(execution, *private_roots):
    if not execution:
        return
    area = Path(execution['root']).resolve()
    for root in private_roots:
        path = Path(root).resolve()
        if area.is_relative_to(path) or path.is_relative_to(area):
            raise ValueError('support_exchange_must_be_separate')


def dispatch(root, command, output, expected, remaining, context, execution):
    from .remote_support_release import inventory, snapshot
    from .remote_support_windows import fresh_directory, acl, current_sid
    validate_execution(execution)
    if current_sid() != execution['controller_sid']:
        raise ValueError('support_controller_identity_mismatch')
    started = time.monotonic()
    timeout = min(command['timeout'], remaining)
    area = Path(execution['root']).resolve()
    # The deployment owner prepares this dedicated root and its ancestor ACLs.
    if not area.is_dir() or area.is_symlink():
        raise ValueError('support_exchange_root_required')
    folder = fresh_directory(area / uuid.uuid4().hex, execution['controller_sid'], execution['worker_sid'])
    snapshot(root, folder / 'source', expected)
    acl(folder / 'source', execution['controller_sid'], execution['worker_sid'], modify=True)
    fresh_directory(folder / 'output', execution['controller_sid'], execution['worker_sid'], modify=True)
    clean = {k:v for k,v in context.items() if k != 'execution'}
    request = {'schema':'cos.local_worker.v1','command':command,'context':clean,
               'expected':expected,'expires_at':time.time()+timeout}
    save(folder / 'request.json', request)  # Publish only after ACLs and copies exist.
    request_digest = digest(request)
    completion = folder / 'output/completed.json'
    while time.monotonic() - started < timeout:
        if completion.is_file():
            break
        time.sleep(0.1)
    result = {'passed':False,'returncode':None,'timed_out':True,'execution_finished':False,
              'source_unchanged':inventory(root, expected)==expected,'context_unchanged':True,
              'worker_result':None,'output':'support_worker_completion_missing','output_truncated':False}
    if completion.is_file():
        response = load(completion)
        if response['request_digest'] != request_digest or digest(load(folder / 'request.json')) != request_digest:
            raise ValueError('support_exchange_request_changed')
        result = response['result']
        result['execution_finished'] = True
        result['source_unchanged'] &= inventory(root, expected) == expected
        result['source_unchanged'] &= inventory(folder / 'source', expected) == expected
        result['passed'] &= result['source_unchanged']
    result.update(seconds=round(time.monotonic()-started,3), exchange_job=str(folder))
    Path(output).parent.mkdir(parents=True,exist_ok=True)
    Path(output).write_text(result['output'], encoding='utf-8')
    save(Path(output).with_suffix('.exchange.json'), {'request_digest':request_digest,'result':result})
    return result


def work_once(area, *, stop_requested=None):
    """A crash leaves claim.json behind; never blindly execute the job again."""
    from .remote_support_release import run_check
    area = Path(area).resolve()
    results = []
    for folder in sorted(area.iterdir()):
        if stop_requested and stop_requested():
            break
        if not folder.is_dir() or folder.is_symlink():
            continue
        try:
            request_file = owned(folder,'request.json')
            if not request_file.is_file():
                continue
            request = load(request_file)
            if (not isinstance(request, dict) or request.get('schema') != 'cos.local_worker.v1'
                    or request['expires_at'] <= time.time()):
                continue
            output = owned(folder,'output')
            if not output.is_dir():
                continue
            if stop_requested and stop_requested():
                break
            with owned(output,'claim.json').open('x',encoding='utf-8') as stream:
                stream.write(digest(request))
        except FileExistsError:
            continue
        except (ValueError, KeyError, TypeError, OSError) as exc:
            results.append({'job':folder.name,'status':'rejected','reason':type(exc).__name__})
            continue
        try:
            if request['context'].get('execution'):
                raise ValueError('support_nested_worker_forbidden')
            remaining = request['expires_at'] - time.time()
            options = {'stop_requested':stop_requested} if stop_requested else {}
            result = run_check(owned(folder,'source'), request['command'], owned(output,'run.log'),
                               request['expected'], remaining, request['context'], **options)
        except (ValueError, KeyError, TypeError, OSError) as exc:
            # A runner exception may leave child outcome unknown.
            results.append({'job':folder.name,'status':'needs_operator','reason':str(exc)})
            continue
        try:
            save(owned(output,'completed.json'), {'request_digest':digest(request),'result':result})
        except (ValueError, OSError) as exc:
            results.append({'job':folder.name,'status':'needs_operator','reason':type(exc).__name__})
            continue
        results.append({'job':folder.name,'status':'completed','passed':result['passed']})
    return results
