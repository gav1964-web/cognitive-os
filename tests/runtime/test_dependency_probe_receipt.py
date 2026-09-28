from pathlib import Path

from runtime.dependency_probe_receipt import load_verified_probe_receipt, write_probe_receipt


def test_probe_receipt_is_bound_to_profile_and_isolated_python(tmp_path: Path):
    env = tmp_path / "artifacts" / "dependency_envs" / "project" / "target"
    python = env / "Scripts" / "python.exe"
    python.parent.mkdir(parents=True)
    python.write_text("", encoding="utf-8")
    profile = {
        "profile_fingerprint": "abc123",
        "project_root": "source/project",
        "target": "pkg/core.py:load",
    }
    result = {"verified_environment": {"env_dir": env.as_posix(), "python": python.as_posix()}}

    write_probe_receipt(tmp_path, profile, result)

    assert load_verified_probe_receipt(profile, tmp_path)["status"] == "passed"
    assert load_verified_probe_receipt({**profile, "target": "pkg/core.py:other"}, tmp_path) == {}
