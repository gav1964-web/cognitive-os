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
