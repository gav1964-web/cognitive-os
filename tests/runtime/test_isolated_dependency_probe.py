import subprocess

from runtime import isolated_dependency_probe
from runtime.isolated_dependency_probe import (
    run_isolated_dependency_probe,
    validate_dependency_probe_approval,
)
from runtime.isolated_dependency_profile import build_isolated_dependency_profile


def test_approval_must_match_profile_fingerprint_and_packages(tmp_path):
    profile = _profile(tmp_path)
    approval = _approval(profile)
    approval["profile_fingerprint"] = "stale"
    approval["approved_packages"] = ["other"]

    validation = validate_dependency_probe_approval(profile, approval)

    assert validation["status"] == "rejected"
    assert "profile_fingerprint" in validation["errors"]
    assert "package_set" in validation["errors"]


def test_probe_blocks_before_subprocess_without_approval(tmp_path, monkeypatch):
    profile = _profile(tmp_path)
    monkeypatch.setattr(
        isolated_dependency_probe,
        "prepare_probe_env",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("installer must not run")),
    )

    result = run_isolated_dependency_probe(
        workspace_root=tmp_path,
        profile=profile,
        approval=None,
    )

    assert result["status"] == "blocked"
    assert result["phase"] == "approval"


def test_probe_rejects_environment_path_inside_source_project(tmp_path, monkeypatch):
    profile = _profile(tmp_path)
    profile["environment"]["path"] = str(tmp_path / "project" / "unsafe-env")
    monkeypatch.setattr(
        isolated_dependency_probe,
        "prepare_probe_env",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("installer must not run")),
    )

    result = run_isolated_dependency_probe(
        workspace_root=tmp_path,
        profile=profile,
        approval=_approval(profile),
    )

    assert result["status"] == "blocked"
    assert result["phase"] == "path_policy"
    assert result["path_check"]["outside_source_project"] is False


def test_approved_probe_prepares_isolated_env_and_imports_only(tmp_path, monkeypatch):
    profile = _review_profile(tmp_path)
    calls = []

    def fake_prepare(**kwargs):
        calls.append(("prepare", kwargs))
        return {"status": "prepared", "python": str(tmp_path / "fake-python")}

    def fake_run(command, **kwargs):
        calls.append(("run", command, kwargs))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(isolated_dependency_probe, "prepare_probe_env", fake_prepare)
    monkeypatch.setattr(isolated_dependency_probe.subprocess, "run", fake_run)

    result = run_isolated_dependency_probe(
        workspace_root=tmp_path,
        profile=profile,
        approval=_approval(profile),
    )

    assert result["status"] == "passed"
    assert calls[0][1]["allow_install"] is True
    assert calls[0][1]["install_timeout_seconds"] == 240
    assert calls[0][1]["prefer_binary"] is True
    install_plan = calls[0][1]["readiness"]["install_plan"]
    assert install_plan["allowed_packages"] == ["scientific-sdk"]
    assert install_plan["review_packages"] == []
    assert calls[1][1][-1] == "scientific_sdk"
    assert result["invariants"]["source_project_mutation"] is False
    assert result["invariants"]["import_probe_only"] is True


def _profile(root):
    project = root / "project"
    project.mkdir(exist_ok=True)
    (project / "requirements.txt").write_text("attrs>=24\n", encoding="utf-8")
    return build_isolated_dependency_profile(
        project_root=project,
        target="pkg/core.py:normalize",
        missing_modules=["attr"],
    )


def test_failed_import_builds_new_approval_bound_profile(tmp_path, monkeypatch):
    profile = _profile(tmp_path)
    monkeypatch.setattr(
        isolated_dependency_probe,
        "prepare_probe_env",
        lambda **kwargs: {"status": "prepared", "python": str(tmp_path / "fake-python")},
    )

    def fake_run(command, **kwargs):
        if "importlib.metadata" in command[2]:
            return subprocess.CompletedProcess(command, 0, '{"attrs": ["numpy>=1.26"]}', "")
        return subprocess.CompletedProcess(command, 1, "", "ModuleNotFoundError: No module named 'numpy'")

    monkeypatch.setattr(isolated_dependency_probe.subprocess, "run", fake_run)

    result = run_isolated_dependency_probe(
        workspace_root=tmp_path,
        profile=profile,
        approval=_approval(profile),
    )

    follow_up = result["follow_up_profile"]
    assert result["status"] == "failed"
    assert follow_up["missing_modules"] == ["numpy"]
    assert follow_up["status"] == "ready_for_probe"
    assert follow_up["install_plan"]["wheel_packages"] == ["numpy"]
    assert follow_up["manifest_evidence"]["approved_distribution_requirements"] == {
        "attrs": ["numpy>=1.26"]
    }
    assert follow_up["profile_fingerprint"] != profile["profile_fingerprint"]


def test_target_import_builds_follow_up_from_approved_distribution(tmp_path, monkeypatch):
    profile = _profile(tmp_path)
    monkeypatch.setattr(
        isolated_dependency_probe,
        "prepare_probe_env",
        lambda **kwargs: {"status": "prepared", "python": str(tmp_path / "fake-python")},
    )

    def fake_run(command, **kwargs):
        script = command[2]
        if "importlib.metadata" in script:
            return subprocess.CompletedProcess(command, 0, '{"attrs": ["scipy>=1.8"]}', "")
        if "sys.path.insert" in script:
            return subprocess.CompletedProcess(command, 1, "", "ModuleNotFoundError: No module named 'scipy'")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(isolated_dependency_probe.subprocess, "run", fake_run)

    result = run_isolated_dependency_probe(
        workspace_root=tmp_path,
        profile=profile,
        approval=_approval(profile),
    )

    assert result["status"] == "failed"
    assert result["phase"] == "target_import_probe"
    assert result["target_module"] == "pkg.core"
    assert result["follow_up_profile"]["install_plan"]["wheel_packages"] == ["scipy"]


def _approval(profile):
    request = profile["approval_request"]
    return {
        "artifact_type": "DependencyProbeApproval",
        "status": "approved",
        "profile_fingerprint": profile["profile_fingerprint"],
        "approved_packages": request["requested_packages"],
        "scope": request["scope"],
        "authority": "human",
    }


def _review_profile(root):
    project = root / "project"
    project.mkdir(exist_ok=True)
    (project / "requirements.txt").write_text("scientific-sdk>=2\n", encoding="utf-8")
    return build_isolated_dependency_profile(
        project_root=project,
        target="pkg/adapter.py:convert",
        missing_modules=["scientific_sdk"],
    )
