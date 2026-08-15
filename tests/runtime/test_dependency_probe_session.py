from copy import deepcopy

from runtime import dependency_probe_session
from runtime.dependency_probe_session import (
    run_dependency_probe_session,
    validate_dependency_probe_session,
)
from runtime.isolated_dependency_profile import build_isolated_dependency_profile


def test_session_rejects_different_target(tmp_path):
    profile = _profile(tmp_path)
    session = _session(profile)
    session["target"] = "pkg/other.py:run"

    validation = validate_dependency_probe_session(profile, session)

    assert validation["status"] == "rejected"
    assert "target" in validation["errors"]


def test_session_delegates_exact_approvals_across_profiles(tmp_path, monkeypatch):
    first = _profile(tmp_path)
    second = deepcopy(first)
    second["profile_fingerprint"] = "second-profile"
    second["approval_request"]["profile_fingerprint"] = "second-profile"
    approvals = []

    def fake_run(**kwargs):
        approvals.append(kwargs["approval"])
        if len(approvals) == 1:
            return {"status": "failed", "phase": "import_probe", "follow_up_profile": second}
        return {"status": "passed", "phase": "complete"}

    monkeypatch.setattr(dependency_probe_session, "run_isolated_dependency_probe", fake_run)

    result = run_dependency_probe_session(
        workspace_root=tmp_path,
        initial_profile=first,
        session=_session(first),
    )

    assert result["status"] == "passed"
    assert [row["profile_fingerprint"] for row in result["steps"]] == [
        first["profile_fingerprint"], "second-profile"
    ]
    assert approvals[0]["delegated_by_session"] == approvals[1]["delegated_by_session"]
    assert approvals[0]["approved_packages"] == ["attrs"]


def test_session_stops_at_approved_step_limit(tmp_path, monkeypatch):
    profile = _profile(tmp_path)
    session = _session(profile)
    session["max_steps"] = 1
    monkeypatch.setattr(
        dependency_probe_session,
        "run_isolated_dependency_probe",
        lambda **kwargs: {"status": "failed", "follow_up_profile": profile},
    )

    result = run_dependency_probe_session(
        workspace_root=tmp_path,
        initial_profile=profile,
        session=session,
    )

    assert result["status"] == "blocked"
    assert result["session_validation"]["status"] == "max_steps_exceeded"
    assert len(result["steps"]) == 1


def _profile(root):
    project = root / "project"
    project.mkdir(exist_ok=True)
    (project / "requirements.txt").write_text("attrs>=24\n", encoding="utf-8")
    return build_isolated_dependency_profile(
        project_root=project,
        target="pkg/core.py:normalize",
        missing_modules=["attr"],
    )


def _session(profile):
    return {
        "artifact_type": "DependencyProbeSessionApproval",
        "status": "approved",
        "project_root": profile["project_root"],
        "target": profile["target"],
        "allowed_profile_statuses": ["ready_for_probe", "review_required"],
        "max_steps": 5,
        "authority": "human",
    }
