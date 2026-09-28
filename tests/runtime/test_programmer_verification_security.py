from pathlib import Path

from runtime import programmer_verification as verification


def test_command_allowlist_rejects_shell_composition() -> None:
    assert verification.command_allowed("python -m compileall .")
    assert not verification.command_allowed("python -m compileall .; echo PROBE")
    assert not verification.command_allowed("python -m pytest tests/runtime/test_schema.py | more")
    assert not verification.command_allowed("python -c print('PROBE')")


def test_run_command_enforces_allowlist_at_execution_boundary(tmp_path: Path, monkeypatch) -> None:
    def unexpected_run(*_args, **_kwargs):
        raise AssertionError("subprocess must not be called")

    monkeypatch.setattr(verification.subprocess, "run", unexpected_run)

    result = verification.run_command("python -c print('PROBE')", tmp_path)

    assert result["status"] == "failed"
    assert result["stderr_tail"] == "unsafe_or_invalid_command"


def test_run_command_uses_argv_without_shell(tmp_path: Path, monkeypatch) -> None:
    observed = {}

    class Completed:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def fake_run(command, **kwargs):
        observed["command"] = command
        observed["shell"] = kwargs["shell"]
        return Completed()

    monkeypatch.setattr(verification.subprocess, "run", fake_run)
    result = verification.run_command("python -m compileall .", tmp_path)

    assert observed == {"command": ["python", "-m", "compileall", "."], "shell": False}
    assert result["status"] == "passed"


def test_zero_verification_is_not_success(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        verification, "run_executable_acceptance",
        lambda **_kwargs: {"status": "not_requested"},
    )
    result = verification.run_test_result(
        root=tmp_path,
        project_dir=tmp_path,
        source_project_dir=tmp_path,
        implementation_plan={"expected_files": [], "verification_commands": []},
        test_plan={},
        execution_dir=tmp_path,
        run_verification=True,
        max_commands=3,
    )

    assert result["status"] == "not_verified"
    assert result["summary"]["executed"] == 0
