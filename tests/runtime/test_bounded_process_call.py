import time

from runtime.bounded_process_call import run_bounded_process_call


def test_bounded_process_call_returns_serializable_result():
    result, timed_out = run_bounded_process_call(
        pow, args=(2, 3), timeout_seconds=5,
    )

    assert result == 8
    assert timed_out is False


def test_bounded_process_call_terminates_slow_worker():
    result, timed_out = run_bounded_process_call(
        time.sleep, args=(1,), timeout_seconds=0.05,
    )

    assert result is None
    assert timed_out is True
