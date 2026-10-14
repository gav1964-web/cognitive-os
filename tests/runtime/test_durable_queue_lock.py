import os

import pytest

from runtime.durable_queue_lock import QueueLock


def test_queue_lock_recovers_dead_owner(tmp_path) -> None:
    path = tmp_path / "queue.lock"
    path.write_text("999999999", encoding="ascii")

    with QueueLock(path, timeout_seconds=0.1, poll_seconds=0.001):
        assert path.read_text(encoding="ascii") == str(os.getpid())

    assert not path.exists()


def test_queue_lock_does_not_take_live_owner(tmp_path) -> None:
    path = tmp_path / "queue.lock"
    path.write_text(str(os.getpid()), encoding="ascii")

    with pytest.raises(TimeoutError):
        QueueLock(path, timeout_seconds=0.01, poll_seconds=0.001).acquire()


@pytest.mark.parametrize('winerror', [32, 33])
def test_release_retries_reader_conflict_without_stranding_lock(tmp_path, monkeypatch, winerror):
    from pathlib import Path
    path = tmp_path / 'queue.lock'
    lock = QueueLock(path, timeout_seconds=0.1, poll_seconds=0.001)
    lock.acquire()
    original = Path.unlink
    attempts = []

    def unlink(current, *args, **kwargs):
        if current == path:
            attempts.append(current)
            if len(attempts) == 1:
                error = PermissionError('reader still holds file')
                error.winerror = winerror
                raise error
        return original(current, *args, **kwargs)

    monkeypatch.setattr(Path, 'unlink', unlink)
    lock.release()
    assert len(attempts) == 2
    assert lock.fd is None and not path.exists()
    with QueueLock(path, timeout_seconds=0.1):
        assert path.exists()
    assert not path.exists()


@pytest.mark.parametrize('winerror', [None, 5, 32])
def test_release_retains_permanent_errors_and_bounds_retry(tmp_path, monkeypatch, winerror):
    from pathlib import Path
    path = tmp_path / 'queue.lock'
    lock = QueueLock(path, timeout_seconds=0, poll_seconds=0.001)
    lock.acquire()
    original = Path.unlink
    error = PermissionError('denied')
    if winerror is not None:
        error.winerror = winerror

    def unlink(current, *args, **kwargs):
        if current == path:
            raise error
        return original(current, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, 'unlink', unlink)
        with pytest.raises(PermissionError) as caught:
            lock.release()
        assert caught.value is error
    assert lock.fd is None and path.exists()
    path.unlink()
