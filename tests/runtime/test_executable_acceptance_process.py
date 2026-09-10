import subprocess

from runtime import executable_acceptance_process as process_boundary


class _StuckProcess:
    pid = 123
    stdin = None
    stdout = None
    stderr = None

    def wait(self, *, timeout):
        raise subprocess.TimeoutExpired("worker", timeout)


def test_isolated_timeout_terminates_process_tree(monkeypatch, tmp_path):
    stuck = _StuckProcess()
    terminated = []
    monkeypatch.setattr(process_boundary.subprocess, "Popen", lambda *args, **kwargs: stuck)
    monkeypatch.setattr(
        process_boundary, "_terminate_process_tree", lambda process: terminated.append(process)
    )

    result = process_boundary.run_executable_acceptance_process(
        root=tmp_path,
        project_dir=tmp_path,
        test_plan={},
        work_dir=tmp_path / "work",
        timeout_seconds=2,
    )

    assert terminated == [stuck]
    assert result["status"] == "failed"
    assert result["summary"]["reason"] == "isolated_process_failed"
    assert "timed out after 2s" in result["summary"]["detail"]


def test_non_utf8_worker_output_becomes_diagnostic_failure(monkeypatch, tmp_path):
    class NoisyProcess:
        pid = 124

        def wait(self, *, timeout):
            return 0

    def launch(*args, **kwargs):
        kwargs["stdout"].write(b"\xc0broken")
        kwargs["stderr"].write(b"\xffdetail")
        return NoisyProcess()

    monkeypatch.setattr(process_boundary.subprocess, "Popen", launch)
    result = process_boundary.run_executable_acceptance_process(
        root=tmp_path,
        project_dir=tmp_path,
        test_plan={},
        work_dir=tmp_path / "work",
        timeout_seconds=2,
    )

    assert result["status"] == "failed"
    assert result["summary"]["reason"] == "isolated_process_invalid_result"
    assert "detail" in result["summary"]["detail"]
