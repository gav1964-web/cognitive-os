"""Restore host plugin imports after a trusted in-process workspace call.

Python's import table is process-global. Direct plugin calls share this lock;
process-bound calls do not change the parent's import state or acquire it.
This is import hygiene, not a security sandbox for arbitrary plugin code.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import importlib
import inspect
from pathlib import Path
import sys
import threading


_IMPORT_LOCK = threading.RLock()
_SESSION = ContextVar('plugin_import_session', default=None)


def plugin_import_session(function):
    """Keep plugin globals across nodes/retries of one pipeline, never the host.

asyncio.to_thread copies the context and shares this session's module table;
the import lock protects that table across concurrent DAG nodes.
"""
    @contextmanager
    def session(root):
        token = _SESSION.set((Path(root).resolve(), {}))
        try:
            yield
        finally:
            _SESSION.reset(token)

    @wraps(function)
    async def async_call(root, *args, **kwargs):
        with session(root):
            return await function(root, *args, **kwargs)

    @wraps(function)
    def sync_call(root, *args, **kwargs):
        with session(root):
            return function(root, *args, **kwargs)

    return async_call if inspect.iscoroutinefunction(function) else sync_call


def _plugin_modules():
    return {name: module for name, module in sys.modules.copy().items()
            if name == 'plugins' or name.startswith('plugins.')}


@contextmanager
def plugin_import_scope(root: Path):
    """Select one workspace for a synchronous call and restore on every exit.

The lock spans the call, including lazy imports. Async executors enter this
scope inside their worker thread, so cancellation cannot restore imports while
that thread is still running. Use process boundaries for parallel isolation.
"""
    with _IMPORT_LOCK:
        previous = _plugin_modules()
        path_object, path_before = sys.path, list(sys.path)
        root = root.resolve()
        root_text = str(root)
        session = _SESSION.get()
        retained = session[1] if session is not None and session[0] == root else {}
        try:
            sys.path[:] = [root_text, *(p for p in sys.path if p != root_text)]
            for name in previous:
                sys.modules.pop(name, None)
            sys.modules.update(retained)
            importlib.invalidate_caches()
            yield
        finally:
            current = _plugin_modules()
            retained.clear()
            retained.update(current)
            for name in current:
                sys.modules.pop(name, None)
            sys.modules.update(previous)
            path_object[:] = path_before
            sys.path = path_object
            importlib.invalidate_caches()
