from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from runtime.historical_defect_environment import prepare_environment, validate_environment_profile
from runtime.historical_defect_process import isolated_environment, run_command
from runtime.local_historical_defect_evidence import evidence_digest
from tests.runtime.historical_defect_environment_helpers import test_environment_profile as _profile


def test_environment_uses_only_frozen_wheels_and_ignores_host_plugins(tmp_path: Path, monkeypatch) -> None:
    profile = _profile(tmp_path)
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setenv("PYTHONPATH", str(tmp_path / "host"))
    monkeypatch.setenv("PYTEST_PLUGINS", "unavailable_host_plugin")
    python, receipt = prepare_environment(
        root=tmp_path, project=project, directory=tmp_path / "environment", profile=profile, timeout=60,
    )
    env = isolated_environment(tmp_path / "tmp", python)
    result = run_command(
        [str(python), "-I", "-c", "import pytest,sys,json;print(json.dumps(sys.path))"],
        cwd=project, env=env, timeout=10,
    )

    assert result["returncode"] == 0, result
    assert receipt["kind"] == "isolated_venv"
    assert receipt["network_install"] is False
    assert receipt["packages"] == {row["name"]: row["version"] for row in profile["wheels"]}
    assert "PYTHONPATH" not in env and "PYTEST_PLUGINS" not in env
    assert all("site-packages" not in path or str(tmp_path) in path for path in json.loads(result["stdout"]))


def test_modified_wheel_is_rejected_before_environment_creation(tmp_path: Path) -> None:
    profile = _profile(tmp_path)
    (tmp_path / profile["wheels"][0]["path"]).write_bytes(b"changed wheel")

    with pytest.raises(ValueError, match="wheel digest mismatch"):
        prepare_environment(root=tmp_path, project=tmp_path, directory=tmp_path / "env",
                            profile=profile, timeout=10)
    assert not (tmp_path / "env").exists()


def test_python_requirement_is_checked_before_install(tmp_path: Path) -> None:
    profile = _profile(tmp_path)
    project = tmp_path / "project"
    project.mkdir()
    (project / "pyproject.toml").write_text("[project]\nrequires-python='>=99'\n", encoding="utf-8")

    with pytest.raises(ValueError, match="project_requires_python"):
        prepare_environment(root=tmp_path, project=project, directory=tmp_path / "env",
                            profile=profile, timeout=10)
    assert not (tmp_path / "env").exists()


def test_unavailable_dependency_closure_is_not_ready(tmp_path: Path) -> None:
    profile = _profile(tmp_path)
    profile["wheels"] = [row for row in profile["wheels"] if row["name"] == "pytest"]
    profile["profile_digest"] = evidence_digest({k: v for k, v in profile.items() if k != "profile_digest"})
    project = tmp_path / "project"
    project.mkdir()

    with pytest.raises(ValueError, match="dependency closure"):
        prepare_environment(root=tmp_path, project=project, directory=tmp_path / "env",
                            profile=profile, timeout=30)


def test_environment_version_drift_is_rejected(tmp_path: Path) -> None:
    profile = _profile(tmp_path)
    profile["python_version"] = "0.0.0"
    profile["profile_digest"] = evidence_digest({k: v for k, v in profile.items() if k != "profile_digest"})

    with pytest.raises(ValueError, match="Python version differs"):
        validate_environment_profile(tmp_path, profile)


def test_bounded_runner_terminates_descendants(tmp_path: Path) -> None:
    marker = tmp_path / "leaked.txt"
    child = "import time,pathlib;time.sleep(2);pathlib.Path(" + repr(str(marker)) + ").write_text('leaked')"
    parent = "import subprocess,sys,time;subprocess.Popen([sys.executable,'-c'," + repr(child) + "]);time.sleep(20)"
    result = run_command([sys.executable, "-c", parent], cwd=tmp_path, timeout=1)
    run_command([sys.executable, "-c", "import time;time.sleep(2)"], cwd=tmp_path, timeout=5)

    assert result["returncode"] == 124
    assert not marker.exists()
