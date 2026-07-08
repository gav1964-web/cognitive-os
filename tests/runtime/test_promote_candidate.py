from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


def test_promote_candidate_registers_active_plugin(tmp_path):
    workspace = _copy_workspace(tmp_path)
    _generate(workspace, "candidate_echo")

    result = _promote(workspace, "candidate_echo")

    registry = json.loads((workspace / "registry" / "capabilities.json").read_text(encoding="utf-8"))
    normalize = _capability(registry, "candidate_echo")
    assert "promoted" in result.stdout
    assert (workspace / "plugins" / "candidate_echo" / "plugin.json").exists()
    assert normalize["lifecycle_status"] == "active"
    reports = list((workspace / "artifacts" / "promotions").glob("candidate_echo_*.json"))
    assert reports
    report = json.loads(reports[0].read_text(encoding="utf-8"))
    assert report["dependency_probe"]["status"] == "passed"
    assert report["quality_gate"]["status"] == "passed"
    assert report["spec"]["id"] == "candidate_echo"


def test_promote_dry_run_does_not_register_plugin(tmp_path):
    workspace = _copy_workspace(tmp_path)
    _generate(workspace, "candidate_echo")

    result = _promote(workspace, "candidate_echo", "--dry-run")

    assert "dry_run_passed" in result.stdout
    assert not (workspace / "plugins" / "candidate_echo").exists()


def test_promote_rejects_invalid_candidate(tmp_path):
    workspace = _copy_workspace(tmp_path)
    _generate(workspace, "candidate_echo")
    (workspace / "generated" / "candidates" / "candidate_echo" / "schemas" / "output.json").unlink()

    result = _promote(workspace, "candidate_echo", check=False)

    assert result.returncode != 0
    assert "missing required file" in result.stderr
    assert not (workspace / "plugins" / "candidate_echo").exists()


def test_promote_requires_negative_tests(tmp_path):
    workspace = _copy_workspace(tmp_path)
    _generate(workspace, "candidate_echo")
    (workspace / "generated" / "candidates" / "candidate_echo" / "tests" / "test_negative.py").unlink()

    result = _promote(workspace, "candidate_echo", check=False)

    assert result.returncode != 0
    assert "tests/test_negative.py" in result.stderr
    assert not (workspace / "plugins" / "candidate_echo").exists()


def test_promote_refuses_existing_plugin_without_force(tmp_path):
    workspace = _copy_workspace(tmp_path)
    _generate(workspace, "candidate_echo")
    _promote(workspace, "candidate_echo")

    result = _promote(workspace, "candidate_echo", check=False)

    assert result.returncode != 0
    assert "plugin already exists" in result.stderr


def test_promote_force_replaces_existing_plugin(tmp_path):
    workspace = _copy_workspace(tmp_path)
    _generate(workspace, "candidate_echo")
    _promote(workspace, "candidate_echo")
    readme = workspace / "plugins" / "candidate_echo" / "README.md"
    readme.write_text("stale", encoding="utf-8")

    result = _promote(workspace, "candidate_echo", "--force")

    assert result.returncode == 0
    assert not readme.exists()


def _copy_workspace(tmp_path: Path) -> Path:
    source = Path(__file__).resolve().parents[2]
    workspace = tmp_path / "workspace"
    for name in ("runtime", "tools", "plugins", "pipelines", "registry", "generated"):
        src = source / name
        dst = workspace / name
        if src.is_dir():
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    (workspace / "artifacts").mkdir(parents=True, exist_ok=True)
    return workspace


def _generate(workspace: Path, plugin_id: str) -> subprocess.CompletedProcess[str]:
    tool = workspace / "tools" / "generate_plugin_candidate.py"
    return subprocess.run(
        [sys.executable, str(tool), "--root", str(workspace), "--id", plugin_id],
        check=True,
        capture_output=True,
        text=True,
    )


def _promote(workspace: Path, plugin_id: str, *extra: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    tool = workspace / "tools" / "promote_candidate.py"
    return subprocess.run(
        [sys.executable, str(tool), "--root", str(workspace), "--id", plugin_id, *extra],
        check=check,
        capture_output=True,
        text=True,
    )


def _capability(registry: dict[str, object], plugin_id: str) -> dict[str, object]:
    for item in registry["capabilities"]:
        if item["id"] == plugin_id:
            return item
    raise AssertionError(f"capability not found: {plugin_id}")
