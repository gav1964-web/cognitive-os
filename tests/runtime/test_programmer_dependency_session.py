import json
from pathlib import Path

from runtime import programmer_dependency_session
from runtime import programmer_executor
from runtime.isolated_dependency_profile import build_isolated_dependency_profile
from runtime.programmer_dependency_session import run_executor_dependency_session
from runtime.programmer_dependency_session import run_dependency_environment_verification
from runtime.programmer_patch_strategy import build_patch_strategy
from runtime.programmer_executor import run_programmer_executor


def test_strategy_emits_bounded_session_request_for_complete_profile(tmp_path):
    (tmp_path / "requirements.txt").write_text("attrs>=24\n", encoding="utf-8")
    profile = build_isolated_dependency_profile(
        project_root=tmp_path,
        target="pkg/core.py:normalize",
        missing_modules=["attr"],
    )

    proposal = build_patch_strategy(
        project_dir=tmp_path,
        technical_spec={},
        implementation_plan={
            "implementation_target": {"candidate": "pkg/core.py:normalize"},
            "dependency_boundary_profile": {
                "status": "resolution_required",
                "isolated_environment_profile": profile,
            },
            "first_slice_reselection_request": {"status": "required", "terminal": True},
        },
        test_plan={},
        synthesis={"status": "skipped"},
        acceptance_summary={"skipped_reason_counts": {"import_failed_missing_module": 1}},
    )

    request = proposal["dependency_probe_session_request"]
    assert request["status"] == "approval_required"
    assert request["project_root"] == profile["project_root"]
    assert request["initial_profile_fingerprint"] == profile["profile_fingerprint"]
    assert request["max_steps"] == 20


def test_executor_adapter_runs_session_only_with_explicit_approval(tmp_path, monkeypatch):
    strategy = {
        "dependency_boundary_profile": {
            "isolated_environment_profile": {"status": "ready_for_probe"},
        }
    }
    approval = {
        "artifact_type": "DependencyProbeSessionApproval",
        "initial_profile_fingerprint": "profile-1",
    }
    calls = []
    monkeypatch.setattr(
        programmer_dependency_session,
        "run_dependency_probe_session",
        lambda **kwargs: calls.append(kwargs) or {"status": "passed"},
    )

    skipped = run_executor_dependency_session(root=tmp_path, strategy=strategy, approval=None)
    result = run_executor_dependency_session(root=tmp_path, strategy=strategy, approval=approval)

    assert skipped == {}
    assert result["status"] == "passed"
    assert calls[0]["session"] == approval


def test_programmer_executor_persists_dependency_session_result(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("def normalize(value):\n    return value\n", encoding="utf-8")
    approval = {
        "artifact_type": "DependencyProbeSessionApproval",
        "status": "approved",
        "initial_profile_fingerprint": "profile-1",
    }
    monkeypatch.setattr(
        programmer_executor,
        "run_executor_dependency_session",
        lambda **kwargs: {"artifact_type": "DependencyProbeSessionResult", "status": "passed", "steps": []},
    )

    result = run_programmer_executor(
        root=tmp_path,
        project_dir=project,
        technical_spec={"artifact_type": "TechnicalSpec"},
        implementation_plan={
            "artifact_type": "ImplementationPlan",
            "implementation_target": {"candidate": "main.py:normalize"},
            "patch_intent": {"target_symbol": "main.py:normalize"},
            "writable_scope": ["main.py:normalize"],
            "expected_files": ["main.py"],
        },
        test_plan={"artifact_type": "TestPlan", "executable_acceptance": {"obligations": []}},
        run_verification=False,
        dependency_probe_session_approval=approval,
    )

    session_path = Path(result["dependency_probe_session_result_path"])
    test_result = json.loads(Path(result["test_result_path"]).read_text(encoding="utf-8"))
    assert session_path.is_file()
    assert json.loads(session_path.read_text(encoding="utf-8"))["status"] == "passed"
    assert test_result["dependency_probe_session_result"]["status"] == "passed"


def test_dependency_environment_verification_uses_verified_python(tmp_path, monkeypatch):
    python = tmp_path / "env" / "python"
    python.parent.mkdir()
    python.write_text("", encoding="utf-8")
    calls = []
    monkeypatch.setattr(
        programmer_dependency_session,
        "run_test_result",
        lambda **kwargs: calls.append(kwargs) or {
            "artifact_type": "TestResult",
            "status": "ok",
            "executable_acceptance_result": {"summary": {"callable_harness_count": 1}},
        },
    )

    result = run_dependency_environment_verification(
        root=tmp_path,
        project_dir=tmp_path,
        source_project_dir=tmp_path,
        implementation_plan={},
        test_plan={},
        execution_dir=tmp_path / "execution",
        session_result={
            "status": "passed",
            "verified_environment": {"python": python.as_posix()},
        },
        run_verification=True,
        max_commands=3,
    )

    assert result["status"] == "ok"
    assert calls[0]["python_executable"] == python
    assert calls[0]["execution_dir"].name == "dependency_environment_verification"


def test_executor_fails_when_dependency_environment_verification_fails(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("def normalize(value):\n    return value\n", encoding="utf-8")
    monkeypatch.setattr(
        programmer_executor,
        "run_executor_dependency_session",
        lambda **kwargs: {"artifact_type": "DependencyProbeSessionResult", "status": "passed"},
    )
    monkeypatch.setattr(
        programmer_executor,
        "run_dependency_environment_verification",
        lambda **kwargs: {"artifact_type": "TestResult", "status": "failed"},
    )

    result = run_programmer_executor(
        root=tmp_path,
        project_dir=project,
        technical_spec={},
        implementation_plan={
            "implementation_target": {"candidate": "main.py:normalize"},
            "patch_intent": {"target_symbol": "main.py:normalize"},
            "writable_scope": ["main.py:normalize"],
            "expected_files": ["main.py"],
        },
        test_plan={"executable_acceptance": {"obligations": []}},
        run_verification=False,
        dependency_probe_session_approval={"status": "approved"},
    )

    test_result = json.loads(Path(result["test_result_path"]).read_text(encoding="utf-8"))
    assert result["status"] == "failed"
    assert test_result["summary"]["dependency_environment_verification"] == "failed"
