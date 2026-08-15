"""Approval-gated preparation and import probing of isolated dependencies."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from .isolated_dependency_profile import build_isolated_dependency_profile
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
    result = {
        "artifact_type": "DependencyProbeApprovalValidation",
        "status": "accepted" if not errors else "rejected",
        "profile_fingerprint": profile.get("profile_fingerprint"),
        "checks": checks,
        "errors": errors,
    }
    return result


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
    environment = dict(profile.get("environment") or {})
    prepared = prepare_probe_env(
        env_dir=Path(str(path_check["env_dir"])),
        readiness=readiness,
        allow_install=True,
        install_timeout_seconds=int(environment.get("install_timeout_seconds") or 240),
        prefer_binary=bool(environment.get("prefer_binary", False)),
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
        probe = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=int(environment.get("import_timeout_seconds") or 60),
        )
    except subprocess.TimeoutExpired as exc:
        return {
            **base,
            "status": "failed",
            "phase": "import_probe",
            "reason": "timeout",
            "stderr": str(exc.stderr or "")[-1200:],
        }
    result = {
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
    target_module = _target_module(str(profile.get("target") or ""))
    if probe.returncode == 0 and target_module:
        try:
            target_probe = subprocess.run(
                [
                    str(prepared["python"]),
                    "-c",
                    "import importlib,sys;sys.path.insert(0,sys.argv[1]);importlib.import_module(sys.argv[2])",
                    str(profile.get("project_root") or ""),
                    target_module,
                ],
                capture_output=True,
                text=True,
                timeout=int(environment.get("import_timeout_seconds") or 60),
            )
        except subprocess.TimeoutExpired as exc:
            return {
                **result,
                "status": "failed",
                "phase": "target_import_probe",
                "reason": "timeout",
                "target_module": target_module,
                "stderr": str(exc.stderr or "")[-1200:],
            }
        result.update({
            "status": "passed" if target_probe.returncode == 0 else "failed",
            "phase": "complete" if target_probe.returncode == 0 else "target_import_probe",
            "target_module": target_module,
            "returncode": target_probe.returncode,
            "stdout": target_probe.stdout[-1200:],
            "stderr": target_probe.stderr[-1200:],
        })
    missing = _missing_module(str(result.get("stderr") or "")) if result["status"] == "failed" else ""
    if missing:
        transitive_evidence = dict(
            dict(profile.get("manifest_evidence") or {}).get("approved_distribution_requirements") or {}
        )
        transitive_evidence.update(_installed_requirement_evidence(
            str(prepared["python"]),
            list(dict(profile.get("approval_request") or {}).get("requested_packages") or []),
        ))
        result["follow_up_profile"] = build_isolated_dependency_profile(
            project_root=profile.get("project_root"),
            target=str(profile.get("target") or ""),
            missing_modules=[missing],
            transitive_evidence=transitive_evidence,
        )
    return result


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


def _missing_module(stderr: str) -> str:
    match = re.search(r"No module named ['\"]([^'\"]+)['\"]", str(stderr or ""))
    return str(match.group(1)).split(".", 1)[0] if match else ""


def _target_module(target: str) -> str:
    path = str(target).split(":", 1)[0].replace("\\", "/").strip("/")
    return path[:-3].replace("/", ".") if path.endswith(".py") else ""


def _installed_requirement_evidence(python: str, packages: list[str]) -> dict[str, list[str]]:
    script = (
        "import importlib.metadata as m,json,sys;"
        "from pip._vendor.packaging.requirements import Requirement as R;"
        "active=lambda s:(R(s).marker is None or R(s).marker.evaluate({'extra':''}));"
        "print(json.dumps({p:[s for s in (m.requires(p) or []) if active(s)] for p in sys.argv[1:]}))"
    )
    probe = subprocess.run(
        [python, "-c", script, *packages], capture_output=True, text=True, timeout=30,
    )
    if probe.returncode != 0:
        return {}
    try:
        payload = json.loads(probe.stdout)
    except (json.JSONDecodeError, TypeError):
        return {}
    return {
        str(package): [str(requirement) for requirement in list(requirements or [])]
        for package, requirements in dict(payload).items()
    }
