"""Behavior and rejection boundaries for the training disconnect repair."""
import asyncio

import pytest

from runtime.programmer_pending_future_patch import complete_pending_futures_on_disconnect
from runtime.programmer_patch_synthesizer import synthesize_patch_package

SOURCE = '''import asyncio
class Protocol:
    def __init__(self):
        self.waiters: dict[int, asyncio.Future] = {}
        self.writer = None
        self.closed = asyncio.Event()
    def register(self, key, waiter: asyncio.Future):
        self.waiters[key] = waiter
    def connection_lost(self, exc):
        if self.writer is not None:
            self.writer.cancel()
        self.closed.set()
'''


@pytest.mark.parametrize('reason', [None, ConnectionResetError('reset'), RuntimeError('transport failed')])
def test_settles_pending_preserves_completed_and_cancelled(reason):
    result = complete_pending_futures_on_disconnect(SOURCE, 'Protocol.connection_lost')
    scope = {}
    exec(result['source'], scope)
    protocol = scope['Protocol']()
    loop = asyncio.BaseEventLoop()
    pending, done, cancelled = [loop.create_future() for _ in range(3)]
    done.set_result('original response')
    cancelled.cancel()
    protocol.register(1, pending)
    protocol.register(2, done)
    protocol.register(3, cancelled)
    try:
        protocol.connection_lost(reason)
        assert pending.done()
        if reason is not None:
            assert pending.exception() is reason
        else:
            assert isinstance(pending.exception(), ConnectionError)
        assert done.result() == 'original response'
        assert cancelled.cancelled()
        assert protocol.closed.is_set()
        protocol.connection_lost(None)
        assert done.result() == 'original response'
    finally:
        loop.close()


def test_empty_map_still_cancels_writer_and_closes():
    result = complete_pending_futures_on_disconnect(SOURCE, 'Protocol.connection_lost')
    scope = {}
    exec(result['source'], scope)
    protocol = scope['Protocol']()
    class Writer:
        cancelled = False
        def cancel(self):
            self.cancelled = True
    protocol.writer = Writer()
    protocol.connection_lost(None)
    assert protocol.writer.cancelled and protocol.closed.is_set()


@pytest.mark.parametrize('source', [
    SOURCE.replace(': dict[int, asyncio.Future]', ''),
    SOURCE.replace(': dict[int, asyncio.Future]', ': list[asyncio.Future]'),
    SOURCE.replace('waiter: asyncio.Future', 'waiter'),
    SOURCE.replace('self.waiters[key] = waiter', 'self.waiters[key] = None'),
    SOURCE.replace('self.closed.set()', 'self.closed.set()\n        self.waiters.clear()'),
    SOURCE.replace('def connection_lost', '@staticmethod\n    def connection_lost'),
    SOURCE.replace('self.writer.cancel()', 'self.writer.cancel("reason")'),
    SOURCE.replace('self.writer is not None', 'self.writer is None'),
    SOURCE + '\nConnectionError = ValueError\n',
    SOURCE + '\npending_future = None\n',
    SOURCE.replace('self.writer = None', 'self.other: dict[int, asyncio.Future] = {}\n        self.writer = None'),
])
def test_unsupported_or_shadowed_source_is_rejected(source):
    assert complete_pending_futures_on_disconnect(source, 'Protocol.connection_lost') is None


def test_patch_does_not_change_registration_and_cannot_be_applied_twice():
    result = complete_pending_futures_on_disconnect(SOURCE, 'Protocol.connection_lost')
    assert result['source'].split('    def connection_lost')[0] == SOURCE.split('    def connection_lost')[0]
    assert complete_pending_futures_on_disconnect(result['source'], 'Protocol.connection_lost') is None
    assert complete_pending_futures_on_disconnect(SOURCE, 'Other.connection_lost') is None


@pytest.mark.parametrize('authorized', [False, True])
def test_synthesizer_requires_explicit_training_authority(tmp_path, authorized):
    project = tmp_path / 'project'
    project.mkdir()
    (project / 'client.py').write_text(SOURCE)
    operation = 'complete_pending_futures_on_disconnect'
    plan = {
        'implementation_target': {'candidate': 'client.py:Protocol.connection_lost'},
        'patch_intent': {'target_symbol': 'client.py:Protocol.connection_lost'},
        'expected_files': ['client.py'],
        'implementation_delta': {'intent': {'operator_id': operation, 'allowed_operator_ids': [operation]}},
    }
    if authorized:
        plan['implementation_delta']['intent']['authority'] = 'explicit_training_replay'
    result = synthesize_patch_package(
        execution_dir=tmp_path / 'execution', project_dir=project,
        implementation_plan=plan, test_plan={},
    )
    assert result['status'] == ('prepared' if authorized else 'blocked')
    if not authorized:
        assert result['reason'] == 'training_replay_authority_required'
    assert (project / 'client.py').read_text() == SOURCE
