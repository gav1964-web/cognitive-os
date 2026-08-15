"""Build a non-executing isolated environment plan from project manifests."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .project_probe_env import dependency_module_plan
from .project_probe_env_policy import load_project_probe_env_policy


def build_isolated_dependency_profile(
    *,
    project_root: str | Path | None,
    target: str | None,
    missing_modules: list[str],
    transitive_evidence: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    modules = list(dict.fromkeys(str(item) for item in missing_modules if item))
    base = {
        "artifact_type": "IsolatedDependencyProfile",
        "target": target,
        "missing_modules": modules,
    }
    if not modules:
        return {**base, "status": "not_required"}
    root = Path(str(project_root or ""))
    if not project_root or not root.is_dir():
        return {
            **base,
            "status": "project_root_unavailable",
            "authority": "diagnostic_only_no_install",
        }
    transitive_evidence = dict(transitive_evidence or {})
    transitive_packages = {
        _requirement_name(requirement)
        for requirements in transitive_evidence.values()
        for requirement in requirements
    } - {""}
    plan = dependency_module_plan(root, modules, additional_declared_packages=transitive_packages)
    install_plan = dict(plan.get("install_plan") or {})
    status = _profile_status(install_plan)
    policy = dict(load_project_probe_env_policy()["isolated_dependency_profile"])
    env_path = str(policy["env_path_template"]).format(
        project=root.name,
        target_hash=hashlib.sha256(str(target or "").encode("utf-8")).hexdigest()[:12],
    )
    profile = {
        **base,
        "status": status,
        "project_root": root.resolve().as_posix(),
        "manifest_evidence": {
            "dependency_files": list(plan.get("dependency_files") or []),
            "declared_packages": list(plan.get("declared_packages") or []),
            "approved_distribution_requirements": transitive_evidence,
        },
        "package_candidates": list(plan.get("install_candidates") or []),
        "install_plan": install_plan,
        "environment": {
            "kind": policy["environment_kind"],
            "path": env_path,
            "outside_source_project": True,
            "automatic_install_allowed": bool(policy.get("automatic_install_allowed", False)),
            "execution_status": "not_executed",
            "install_timeout_seconds": int(policy["install_timeout_seconds"]),
            "import_timeout_seconds": int(policy["import_timeout_seconds"]),
            "prefer_binary": bool(policy.get("prefer_binary", False)),
        },
        "verification_gates": list(policy["verification_gates"]),
        "forbidden_actions": list(policy["forbidden_actions"]),
        "authority": "profile_plan_only_explicit_install_permission_required",
        "next_step": _next_step(status),
    }
    fingerprint = _profile_fingerprint(profile)
    profile["profile_fingerprint"] = fingerprint
    profile["approval_request"] = _approval_request(profile, policy, fingerprint)
    return profile


def _profile_status(install_plan: dict[str, Any]) -> str:
    if install_plan.get("blocked_packages"):
        return "blocked_undeclared"
    if install_plan.get("review_packages") or install_plan.get("native_packages"):
        return "review_required"
    if install_plan.get("allowed_packages") or install_plan.get("wheel_packages"):
        return "ready_for_probe"
    return "blocked_no_install_candidate"


def _requirement_name(requirement: str) -> str:
    match = re.match(r"\s*([A-Za-z0-9_.-]+)", str(requirement))
    return match.group(1).replace("_", "-").lower() if match else ""


def _next_step(status: str) -> str:
    return {
        "ready_for_probe": "request_explicit_permission_then_prepare_isolated_environment",
        "review_required": "review_declared_dependency_risk_then_accept_or_reject_profile",
        "blocked_undeclared": "return_to_dependency_contract_review",
    }.get(status, "review_dependency_mapping_and_manifest_evidence")


def _profile_fingerprint(profile: dict[str, Any]) -> str:
    evidence = {
        "target": profile.get("target"),
        "missing_modules": list(profile.get("missing_modules") or []),
        "manifest_evidence": dict(profile.get("manifest_evidence") or {}),
        "environment": dict(profile.get("environment") or {}),
        "package_candidates": list(profile.get("package_candidates") or []),
        "install_plan": dict(profile.get("install_plan") or {}),
    }
    canonical = json.dumps(evidence, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _approval_request(
    profile: dict[str, Any], policy: dict[str, Any], fingerprint: str
) -> dict[str, Any]:
    plan = dict(profile.get("install_plan") or {})
    packages = sorted({
        str(item)
        for key in ("allowed_packages", "wheel_packages", "review_packages", "native_packages")
        for item in list(plan.get(key) or [])
    })
    return {
        "artifact_type": "DependencyProbeApprovalRequest",
        "status": "approval_required",
        "profile_fingerprint": fingerprint,
        "requested_packages": packages,
        "risk_status": profile.get("status"),
        "scope": policy["approval_scope"],
        "allowed_authorities": list(policy["allowed_authorities"]),
        "constraints": [
            "isolated_environment_only",
            "import_probe_only",
            "source_project_unchanged",
            "approval_invalidated_when_profile_fingerprint_changes",
        ],
    }
