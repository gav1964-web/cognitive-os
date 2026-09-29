"""Single-instance worker lifecycle; SCM adapter supplies the cooperative stop event.

Configuration and exchange namespace must be controller/admin-owned. Heartbeats
are diagnostic only: neither a stopped daemon nor a claim proves paid work settled.
"""
import os
import time
from contextlib import contextmanager
from pathlib import Path

from .remote_support_exchange import work_once
from .remote_support_protocol import load, save
from .remote_support_windows import current_sid, sid


def read_config(path):
    path = Path(path).resolve()
    config = load(path)
    if (not isinstance(config, dict) or set(config) != {
            'schema', 'worker_sid', 'controller_sid', 'exchange', 'state', 'poll_seconds'}
            or config['schema'] != 'cos.worker_service.v1'
            or config['worker_sid'] == config['controller_sid']
            or type(config['poll_seconds']) not in (int, float)
            or not 0.1 <= config['poll_seconds'] <= 10):
        raise ValueError('support_service_config')
    sid(config['worker_sid'])
    sid(config['controller_sid'])
    for name in ('exchange', 'state'):
        target = Path(config[name])
        if not target.is_absolute() or not target.is_dir():
            raise ValueError('support_service_directory')
        # Fixed sibling directories inside the protected deployment namespace.
        if target.resolve() != path.parent / name:
            raise ValueError('support_service_layout')
        for part in (target, *target.parents):
            if part.is_symlink() or (part.stat().st_file_attributes & 0x400
                                     if os.name == 'nt' else False):
                raise ValueError('support_service_reparse_point')
    return config


@contextmanager
def single_instance(state):
    """OS lock survives stale file content, releases when the owning process exits."""
    with (Path(state) / 'worker.lock').open('a+b') as stream:
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ValueError('support_service_already_running') from exc
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def serve(config_path, stop):
    config = read_config(config_path)
    if current_sid() != config['worker_sid']:
        raise ValueError('support_worker_identity_mismatch')
    state = Path(config['state'])
    with single_instance(state):
        def status(phase, rows=()):
            save(state / 'status.json', {'schema':'cos.worker_status.v1',
                'pid':os.getpid(), 'worker_sid':config['worker_sid'],
                'phase':phase, 'updated_at':time.time(), 'jobs':list(rows)[-64:]})
        status('running')
        try:
            while not stop.is_set():
                rows = work_once(config['exchange'], stop_requested=stop.is_set)
                status('stopping' if stop.is_set() else 'running', rows)
                stop.wait(config['poll_seconds'])
        except Exception:
            status('failed')
            raise
        finally:
            if stop.is_set():
                status('stopped')
