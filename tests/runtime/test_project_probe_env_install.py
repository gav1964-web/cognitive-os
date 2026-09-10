from pathlib import Path
import subprocess

from runtime import project_probe_env_install
from runtime.project_probe_env_install import prepare_probe_env


def test_prepare_probe_env_skips_packages_already_installed(tmp_path: Path, monkeypatch):
    env_dir = tmp_path / "env"
    python = env_dir / "Scripts" / "python.exe"
    python.parent.mkdir(parents=True)
    python.write_text("", encoding="utf-8")
    (env_dir / "pyvenv.cfg").write_text("", encoding="utf-8")
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        if "importlib.metadata" in args[2]:
            return subprocess.CompletedProcess(args, 0, '["pytest"]', "")
        raise AssertionError("pip must not run for an installed package")

    monkeypatch.setattr(project_probe_env_install.subprocess, "run", fake_run)
    readiness = {"install_plan": {"allowed_packages": ["pytest"]}}

    result = prepare_probe_env(env_dir=env_dir, readiness=readiness, allow_install=True)

    assert (result["status"], result["already_installed"]) == ("prepared", ["pytest"])
    assert len(calls) == 1


def test_prepare_probe_env_reports_timeout_when_fallback_fails(tmp_path: Path, monkeypatch):
    def fake_run(args, **kwargs):
        if args[:3] == [project_probe_env_install.sys.executable, "-m", "venv"]:
            return subprocess.CompletedProcess(args, 0, "", "")
        raise subprocess.TimeoutExpired(args, 240, stderr="network stalled")

    monkeypatch.setattr(project_probe_env_install.subprocess, "run", fake_run)
    monkeypatch.setattr(
        project_probe_env_install,
        "install_verified_wheels",
        lambda **kwargs: {"status": "error", "reason": "fallback failed"},
    )
    readiness = {"install_plan": {"allowed_packages": ["pytest"]}}

    result = prepare_probe_env(env_dir=tmp_path / "env", readiness=readiness, allow_install=True)

    assert result["status"] == "error"
    assert result["reason"] == "timeout"
    assert result["fallback_result"]["reason"] == "fallback failed"


def test_prepare_probe_env_uses_verified_fallback_after_timeout(tmp_path: Path, monkeypatch):
    def fake_run(args, **kwargs):
        if args[:3] == [project_probe_env_install.sys.executable, "-m", "venv"]:
            return subprocess.CompletedProcess(args, 0, "", "")
        raise subprocess.TimeoutExpired(args, 240)

    monkeypatch.setattr(project_probe_env_install.subprocess, "run", fake_run)
    monkeypatch.setattr(
        project_probe_env_install,
        "install_verified_wheels",
        lambda **kwargs: {
            "status": "installed",
            "artifacts": [{"package": "pytest", "sha256": "abc"}],
        },
    )

    result = prepare_probe_env(
        env_dir=tmp_path / "env",
        readiness={"install_plan": {"allowed_packages": ["pytest"]}},
        allow_install=True,
    )

    assert result["status"] == "prepared"
    assert result["installer"] == "verified_pypi_wheel_fallback"
    assert result["verified_wheels"][0]["sha256"] == "abc"
