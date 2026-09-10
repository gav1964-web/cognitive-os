from __future__ import annotations

import hashlib
from pathlib import Path

from runtime.project_development import load_project_development_policy
from runtime.project_development_authorized_implementation import run_authorized_implementation
from runtime.project_development_implementation_authorization import (
    _artifact_digest,
    build_implementation_authorization_request,
    validate_implementation_authorization,
)
from runtime.programmer_exception_pickle_patch import exception_pickle_reconstruction_patch


def _design(source_sha256: str = "a" * 64) -> dict:
    return {
        "artifact_type": "ProjectDevelopmentImplementationDesign",
        "status": "designed_not_executable",
        "authority": "architect",
        "request_id": "design:candidate:one",
        "candidate_id": "candidate:one",
        "proposal_id": "proposal:one",
        "evidence_digest": "b" * 64,
        "hypothesis_kind": "exception_pickle_reconstruction_boundary",
        "target": "pkg.py:SocketConnectBlockedError.__init__",
        "source_sha256": source_sha256,
        "interface_boundary": {"preserve": True},
        "transformation_steps": ["retain constructor inputs"],
        "acceptance_mapping": [{"check": "pickle round trip"}],
        "rollback_strategy": {"action": "discard sandbox"},
        "constraints": {
            "execution_authorized": False,
            "developer_handoff_allowed": False,
            "executor_rerun_allowed": False,
            "source_changes_allowed": False,
            "memory_promotion_allowed": False,
        },
    }


def _accepted_design_validation(design: dict) -> dict:
    return {
        "status": "accepted_not_executable",
        "design_accepted": True,
        "design_digest": _artifact_digest(design),
    }


def test_authorization_is_bound_to_exact_design_digest():
    policy = load_project_development_policy()
    design = _design()
    design_validation = _accepted_design_validation(design)
    request = build_implementation_authorization_request(
        design=design, design_validation=design_validation, policy=policy
    )
    decision = {
        "artifact_type": "ProjectDevelopmentImplementationAuthorizationDecision",
        "status": "decided",
        "decision": "approve",
        "request_id": request["request_id"],
        "candidate_id": request["candidate_id"],
        "design_digest": request["design_digest"],
        "execution_policy_digest": request["execution_policy_digest"],
        "evidence_digest": request["evidence_digest"],
        "target": request["target"],
        "authority": "human",
        "reason": "Approve one sandbox implementation and verification run",
    }

    accepted = validate_implementation_authorization(
        request=request,
        human_decision=decision,
        design=design,
        design_validation=design_validation,
        policy=policy,
    )
    assert accepted["status"] == "approved"
    assert accepted["sandbox_implementation_authorized"] is True
    assert accepted["source_apply_authorized"] is False

    drifted = dict(design)
    drifted["transformation_steps"] = ["different design"]
    blocked = validate_implementation_authorization(
        request=request,
        human_decision=decision,
        design=drifted,
        design_validation=design_validation,
        policy=policy,
    )
    assert blocked["status"] == "blocked"
    assert "design_digest_matches" in blocked["blocking_reasons"]


def test_exception_pickle_reducer_requires_exact_constructor_shape():
    policy = load_project_development_policy()
    recipe = policy["feedback_policy"]["replan_revision"]["bounded_experiment"][
        "human_approval"
    ]["implementation_design"]["implementation_authorization"]
    source = (
        "class SocketConnectBlockedError(RuntimeError):\n"
        "    def __init__(self, allowed, host, *args, **kwargs):\n"
        "        msg = f'{host}:{allowed}'\n"
        "        super().__init__(msg)\n"
    )
    patch = exception_pickle_reconstruction_patch(
        source, class_name="SocketConnectBlockedError", recipe=recipe
    )
    assert patch is not None
    namespace: dict[str, object] = {}
    exec(patch["source"], namespace)
    error = namespace["SocketConnectBlockedError"](["localhost"], "example.test")
    constructor, arguments = error.__reduce__()
    restored = constructor(*arguments)
    assert type(restored) is type(error)
    assert restored.args == error.args

    assert exception_pickle_reconstruction_patch(
        source.replace("allowed, host", "message, host"),
        class_name="SocketConnectBlockedError",
        recipe=recipe,
    ) is None


def test_authorized_runner_changes_only_sandbox_target(tmp_path: Path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / "pkg.py").write_text(
        "class SocketConnectBlockedError(RuntimeError):\n"
        "    def __init__(self, allowed, host, *args, **kwargs):\n"
        "        msg = f'{host}:{allowed}'\n"
        "        super().__init__(msg)\n",
        encoding="utf-8",
    )
    design = _design(hashlib.sha256((project / "pkg.py").read_bytes()).hexdigest())
    monkeypatch.setattr(
        "runtime.project_development_authorized_implementation.run_project_native_verification",
        lambda **_kwargs: {
            "artifact_type": "ProjectNativeVerificationResult",
            "status": "passed",
            "targeted_replay": {"status": "passed"},
            "regression_suite": {"status": "passed"},
        },
    )
    result = run_authorized_implementation(
        root=tmp_path,
        project_dir=project,
        execution_dir=tmp_path / "execution",
        design=design,
        authorization_validation={
            "status": "approved",
            "sandbox_implementation_authorized": True,
            "source_apply_authorized": False,
        },
        failing_nodeids=["tests/test_pkg.py::test_pickle"],
        policy=load_project_development_policy(),
    )
    assert result["status"] == "verified_in_sandbox"
    assert result["sandbox_changed_python_files"] == ["pkg.py"]
    assert "def __reduce__" not in (project / "pkg.py").read_text(encoding="utf-8")
    assert "def __reduce__" in (
        Path(result["sandbox_project"]) / "pkg.py"
    ).read_text(encoding="utf-8")
    assert result["source_invariant"]["unchanged"] is True
    assert result["source_apply"] is False
    assert result["memory_promotion"] is False


def test_authorized_runner_accepts_design_bound_reuse_recipe(tmp_path: Path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    source = (
        "class LocationParseError(ValueError):\n"
        "    def __init__(self, location):\n"
        "        super().__init__(f'Failed to parse: {location}')\n"
        "        self.location = location\n"
    )
    (project / "pkg.py").write_text(source, encoding="utf-8")
    design = _design(hashlib.sha256((project / "pkg.py").read_bytes()).hexdigest())
    design["target"] = "pkg.py:LocationParseError.__init__"
    design["implementation_recipe"] = {
        "operator_id": "preserve_exception_constructor_reconstruction",
        "required_constructor_inputs": ["location"],
        "reconstruction_method": "__reduce__",
        "state_strategy": "reuse_direct_assignments",
    }
    monkeypatch.setattr(
        "runtime.project_development_authorized_implementation.run_project_native_verification",
        lambda **_kwargs: {
            "status": "passed",
            "targeted_replay": {"status": "passed"},
            "regression_suite": {"status": "passed"},
        },
    )

    result = run_authorized_implementation(
        root=tmp_path,
        project_dir=project,
        execution_dir=tmp_path / "execution",
        design=design,
        authorization_validation={
            "status": "approved",
            "sandbox_implementation_authorized": True,
            "source_apply_authorized": False,
        },
        failing_nodeids=["tests/test_pkg.py::test_pickle"],
        policy=load_project_development_policy(),
    )

    assert result["status"] == "verified_in_sandbox"
    patched = (Path(result["sandbox_project"]) / "pkg.py").read_text(encoding="utf-8")
    assert "return (self.__class__, (self.location,))" in patched


def test_authorized_runner_ignores_generated_build_lib_scope(tmp_path: Path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / "pkg.py").write_text(
        "class SocketConnectBlockedError(RuntimeError):\n"
        "    def __init__(self, allowed, host, *args, **kwargs):\n"
        "        msg = f'{host}:{allowed}'\n"
        "        super().__init__(msg)\n",
        encoding="utf-8",
    )
    design = _design(hashlib.sha256((project / "pkg.py").read_bytes()).hexdigest())

    def fake_verification(**kwargs):
        sandbox = kwargs["project"]
        generated = sandbox / "build" / "lib" / "pkg.py"
        generated.parent.mkdir(parents=True, exist_ok=True)
        generated.write_text("# generated by local wheel build\n", encoding="utf-8")
        return {
            "artifact_type": "ProjectNativeVerificationResult",
            "status": "passed",
            "targeted_replay": {"status": "passed"},
            "regression_suite": {"status": "passed"},
        }

    monkeypatch.setattr(
        "runtime.project_development_authorized_implementation.run_project_native_verification",
        fake_verification,
    )

    result = run_authorized_implementation(
        root=tmp_path,
        project_dir=project,
        execution_dir=tmp_path / "execution",
        design=design,
        authorization_validation={
            "status": "approved",
            "sandbox_implementation_authorized": True,
            "source_apply_authorized": False,
        },
        failing_nodeids=["tests/test_pkg.py::test_pickle"],
        policy=load_project_development_policy(),
    )

    assert result["status"] == "verified_in_sandbox"
    assert result["sandbox_changed_python_files"] == ["pkg.py"]
    assert "build/lib/pkg.py" in result["generated_build_files_removed"]
