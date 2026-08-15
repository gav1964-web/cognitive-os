"""Run a bounded dependency chain under one human session approval."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .isolated_dependency_probe import run_isolated_dependency_probe
from .project_probe_env_policy import load_project_probe_env_policy


def validate_dependency_probe_session(
    profile: dict[str, Any], session: dict[str, Any] | None,
) -> dict[str, Any]:
    session = dict(session or {})
    policy = dict(load_project_probe_env_policy()["isolated_dependency_profile"])
    allowed_by_policy = set(str(item) for item in policy["session_allowed_profile_statuses"])
    allowed_by_session = set(str(item) for item in list(session.get("allowed_profile_statuses") or []))
    try:
        max_steps = int(session.get("max_steps") or 0)
    except (TypeError, ValueError):
        max_steps = 0
    checks = {
        "artifact_type": session.get("artifact_type") == policy["session_approval_artifact_type"],
        "status": session.get("status") == policy["session_approval_status"],
        "project_root": _same_path(session.get("project_root"), profile.get("project_root")),
        "target": session.get("target") == profile.get("target"),
        "authority": session.get("authority") in list(policy["allowed_authorities"]),
        "allowed_statuses": bool(allowed_by_session) and allowed_by_session <= allowed_by_policy,
        "profile_status": profile.get("status") in allowed_by_session,
        "max_steps": 0 < max_steps <= int(policy["session_max_steps"]),
    }
    errors = [name for name, passed in checks.items() if not passed]
    return {
        "artifact_type": "DependencyProbeSessionValidation",
        "status": "accepted" if not errors else "rejected",
        "session_fingerprint": dependency_probe_session_fingerprint(session),
        "checks": checks,
        "errors": errors,
    }


def run_dependency_probe_session(
    *, workspace_root: Path, initial_profile: dict[str, Any], session: dict[str, Any],
) -> dict[str, Any]:
    profile = dict(initial_profile)
    steps = []
    for index in range(1, int(session.get("max_steps") or 0) + 1):
        validation = validate_dependency_probe_session(profile, session)
        if validation["status"] != "accepted":
            return _session_result("blocked", steps, profile, validation)
        approval = _exact_approval(profile, session, validation["session_fingerprint"])
        result = run_isolated_dependency_probe(
            workspace_root=workspace_root,
            profile=profile,
            approval=approval,
        )
        steps.append({
            "step": index,
            "profile_fingerprint": profile.get("profile_fingerprint"),
            "packages": list(approval["approved_packages"]),
            "status": result.get("status"),
            "phase": result.get("phase"),
        })
        if result.get("status") == "passed":
            return _session_result("passed", steps, None, validation)
        profile = dict(result.get("follow_up_profile") or {})
        if not profile:
            return _session_result("failed", steps, None, validation)
    return _session_result("blocked", steps, profile, {"status": "max_steps_exceeded"})


def dependency_probe_session_fingerprint(session: dict[str, Any]) -> str:
    evidence = {
        key: session.get(key)
        for key in (
            "artifact_type", "status", "project_root", "target",
            "allowed_profile_statuses", "max_steps", "authority",
        )
    }
    canonical = json.dumps(evidence, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _exact_approval(
    profile: dict[str, Any], session: dict[str, Any], session_fingerprint: str,
) -> dict[str, Any]:
    request = dict(profile.get("approval_request") or {})
    return {
        "artifact_type": "DependencyProbeApproval",
        "status": "approved",
        "profile_fingerprint": profile.get("profile_fingerprint"),
        "approved_packages": list(request.get("requested_packages") or []),
        "scope": request.get("scope"),
        "authority": session.get("authority"),
        "delegated_by_session": session_fingerprint,
    }


def _session_result(
    status: str, steps: list[dict[str, Any]], next_profile: dict[str, Any] | None,
    validation: dict[str, Any],
) -> dict[str, Any]:
    return {
        "artifact_type": "DependencyProbeSessionResult",
        "status": status,
        "session_validation": validation,
        "steps": steps,
        "next_profile": next_profile,
    }


def _same_path(left: object, right: object) -> bool:
    if not left or not right:
        return False
    return Path(str(left)).resolve() == Path(str(right)).resolve()
