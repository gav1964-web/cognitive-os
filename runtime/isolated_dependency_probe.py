"""Approval-gated preparation and import probing of isolated dependencies."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from .project_probe_env import prepare_probe_env
from .project_probe_env_policy import load_project_probe_env_policy


def validate_dependency_probe_approval(
    profile: dict[str, Any], approval: dict[str, Any] | None
) -> dict[str, Any]:
    policy = dict(load_project_probe_env_policy()["isolated_dependency_profile"])
    request = dict(profile.get("approval_request") or {})
    approval = dict(approval or {})
    errors = []
    expected_packages = sorted(str(item) for item in list(request.get("requested_packages") or []))
    approved_packages = sorted(str(item) for item in list(approval.get("approved_packages") or []))
    checks = {
        "artifact_type": approval.get("artifact_type") == policy["approval_artifact_type"],
        "status": approval.get("status") == policy["approval_status"],
        "profile_fingerprint": approval.get("profile_fingerprint") == profile.get("profile_fingerprint"),
        "scope": approval.get("scope") == policy["approval_scope"],
        "authority": approval.get("authority") in list(policy["allowed_authorities"]),
        "package_set": approved_packages == expected_packages,
    }
    errors.extend(name for name, passed in checks.items() if not passed)
    native = list(dict(profile.get("install_plan") or {}).get("native_packages") or [])
    if native:
        errors.append("native_dependency_requires_platform_specific_runner")
    return {
        "artifact_type": "DependencyProbeApprovalValidation",
        "status": "accepted" if not errors else "rejected",
        "profile_fingerprint": profile.get("profile_fingerprint"),
        "checks": checks,
        "errors": errors,
    }


def run_isolated_dependency_probe(
    *,
    workspace_root: Path,
    profile: dict[str, Any],
    approval: dict[str, Any] | None,
) -> dict[str, Any]:
    validation = validate_dependency_probe_approval(profile, approval)
    base = {
        "artifact_type": "IsolatedDependencyProbeResult",
        "profile_fingerprint": profile.get("profile_fingerprint"),
        "approval_validation": validation,
    }
    if validation["status"] != "accepted":
        return {**base, "status": "blocked", "phase": "approval"}
    path_check = _environment_path(workspace_root, profile)
    if path_check["status"] != "accepted":
        return {**base, "status": "blocked", "phase": "path_policy", "path_check": path_check}
    readiness = _approved_readiness(profile)
    prepared = prepare_probe_env(
        env_dir=Path(str(path_check["env_dir"])),
        readiness=readiness,
        allow_install=True,
    )
    if prepared.get("status") != "prepared":
        return {**base, "status": "failed", "phase": "environment", "environment_result": prepared}
    modules = [str(item) for item in list(profile.get("missing_modules") or [])]
    command = [
        str(prepared["python"]),
        "-c",
        "import importlib,sys; [importlib.import_module(name) for name in sys.argv[1:]]",
        *modules,
    ]
    try:
        probe = subprocess.run(command, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired as exc:
        return {
            **base,
            "status": "failed",
            "phase": "import_probe",
            "reason": "timeout",
            "stderr": str(exc.stderr or "")[-1200:],
        }
    return {
        **base,
        "status": "passed" if probe.returncode == 0 else "failed",
        "phase": "complete" if probe.returncode == 0 else "import_probe",
        "modules": modules,
        "environment_result": prepared,
        "returncode": probe.returncode,
        "stdout": probe.stdout[-1200:],
        "stderr": probe.stderr[-1200:],
        "invariants": {
            "source_project_mutation": False,
            "host_environment_install": False,
            "import_probe_only": True,
        },
    }


def _environment_path(workspace_root: Path, profile: dict[str, Any]) -> dict[str, Any]:
    workspace = workspace_root.resolve()
    allowed_root = (workspace / "artifacts" / "dependency_envs").resolve()
    env_path = Path(str(dict(profile.get("environment") or {}).get("path") or ""))
    env_dir = (workspace / env_path).resolve() if not env_path.is_absolute() else env_path.resolve()
    project_root = Path(str(profile.get("project_root") or "")).resolve()
    accepted = _within(env_dir, allowed_root) and not _within(env_dir, project_root)
    return {
        "status": "accepted" if accepted else "rejected",
        "env_dir": env_dir.as_posix(),
        "allowed_root": allowed_root.as_posix(),
        "outside_source_project": not _within(env_dir, project_root),
    }


def _approved_readiness(profile: dict[str, Any]) -> dict[str, Any]:
    plan = dict(profile.get("install_plan") or {})
    approved = sorted(set(list(plan.get("allowed_packages") or []) + list(plan.get("review_packages") or [])))
    return {
        "install_plan": {
            **plan,
            "allowed_packages": approved,
            "review_packages": [],
        }
    }


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
