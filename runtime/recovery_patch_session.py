"""Operational recovery patch session with post-apply verification and rollback."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contract_registry import ContractRegistry
from .recovery_patch_admission import apply_recovery_patch, rollback_recovery_patch
from .role_pipeline import run_role_pipeline


def run_recovery_patch_session(
    *,
    root: Path,
    project_dir: Path,
    patch_package: dict[str, Any],
    admission: dict[str, Any],
    apply: bool = False,
    approval: dict[str, Any] | None = None,
    write: bool = False,
) -> dict[str, Any]:
    """Dry-run by default; explicit apply is verified by the normal role pipeline."""
    preflight = _preflight(project_dir, patch_package, admission)
    if not apply or not all(preflight.values()):
        report = _report(
            status="ready_to_apply" if all(preflight.values()) else "blocked",
            project_dir=project_dir,
            patch_package=patch_package,
            admission=admission,
            preflight=preflight,
            apply_requested=apply,
            apply_receipt=None,
            post_apply=None,
            rollback_receipt=None,
        )
        return _finish(root, report, write=write)

    receipt = apply_recovery_patch(
        project_dir=project_dir,
        patch_package=patch_package,
        admission=admission,
        approval=approval,
    )
    if receipt.get("status") != "applied":
        report = _report(
            status="blocked",
            project_dir=project_dir,
            patch_package=patch_package,
            admission=admission,
            preflight=preflight,
            apply_requested=True,
            apply_receipt=receipt,
            post_apply=None,
            rollback_receipt=None,
        )
        return _finish(root, report, write=write)

    post_result: dict[str, Any] = {}
    post_error: str | None = None
    try:
        post_result = run_role_pipeline(
            root=root,
            project_dir=project_dir,
            goal=f"Verify applied recovery patch for {project_dir.name}",
            write=False,
        )
    except Exception as exc:  # rollback is more important than propagating verification errors
        post_error = f"{type(exc).__name__}: {exc}"
    post_apply = _post_apply_checks(admission, post_result, post_error)
    rollback = None
    status = "applied_verified"
    if not all(post_apply["checks"].values()):
        rollback = rollback_recovery_patch(project_dir=project_dir, receipt=receipt)
        status = "rolled_back_after_failed_verification" if rollback.get("status") == "rolled_back" else "rollback_failed"
    report = _report(
        status=status,
        project_dir=project_dir,
        patch_package=patch_package,
        admission=admission,
        preflight=preflight,
        apply_requested=True,
        apply_receipt=receipt,
        post_apply=post_apply,
        rollback_receipt=rollback,
    )
    return _finish(root, report, write=write)


def _preflight(
    project_dir: Path, patch_package: dict[str, Any], admission: dict[str, Any]
) -> dict[str, bool]:
    patches = [dict(row) for row in patch_package.get("patches", []) if isinstance(row, dict)]
    relative = str(patches[0].get("file") or "") if len(patches) == 1 else ""
    target = _scoped_file(project_dir, relative)
    digest = str(patch_package.get("patch_digest") or "")
    return {
        "admission_ready": admission.get("status") == "ready_for_human_approval",
        "single_patch": len(patches) == 1,
        "digest_matches_admission": bool(digest) and admission.get("patch_digest") == digest,
        "tester_differential_passed": dict(patch_package.get("differential_verification") or {}).get("status")
        == "passed",
        "automatic_apply_disabled": admission.get("automatic_apply") is False,
        "source_precondition_matches": bool(target and target.is_file())
        and _sha256(target) == patch_package.get("source_precondition_sha256"),
    }


def _post_apply_checks(
    admission: dict[str, Any], result: dict[str, Any], error: str | None
) -> dict[str, Any]:
    quality = dict(result.get("role_quality") or {})
    candidate = str(admission.get("candidate") or "")
    checks = {
        "pipeline_completed": error is None and bool(result),
        "architect_selected_candidate": bool(candidate)
        and quality.get("selected_extraction_candidate") == candidate,
        "implementer_target_preserved": bool(candidate) and quality.get("implementation_target") == candidate,
        "reviewer_approved": result.get("recommendation") in {"approve", "approve_with_risks"},
        "recovery_no_longer_required": dict(result.get("no_safe_candidate_recovery") or {}).get("status")
        == "not_applicable",
    }
    return {
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "error": error,
        "selected_target": quality.get("selected_extraction_candidate"),
        "implementation_target": quality.get("implementation_target"),
        "recommendation": result.get("recommendation"),
    }


def _report(
    *,
    status: str,
    project_dir: Path,
    patch_package: dict[str, Any],
    admission: dict[str, Any],
    preflight: dict[str, bool],
    apply_requested: bool,
    apply_receipt: dict[str, Any] | None,
    post_apply: dict[str, Any] | None,
    rollback_receipt: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "artifact_type": "RecoveryPatchSessionReport",
        "status": status,
        "created_at": _now(),
        "project": project_dir.as_posix(),
        "candidate": admission.get("candidate"),
        "patch_digest": patch_package.get("patch_digest"),
        "preflight": preflight,
        "apply_requested": apply_requested,
        "apply_receipt": apply_receipt,
        "post_apply_verification": post_apply,
        "rollback_receipt": rollback_receipt,
        "safety": {
            "human_approval_required": True,
            "automatic_apply": False,
            "automatic_rollback_on_failed_verification": True,
        },
    }


def _finish(root: Path, report: dict[str, Any], *, write: bool) -> dict[str, Any]:
    ContractRegistry({}).validate_artifact(report)
    if write:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = root / "artifacts" / "recovery_patch_sessions" / f"session_{stamp}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = path.as_posix()
    return report


def _scoped_file(root: Path, relative: str) -> Path | None:
    if not relative:
        return None
    resolved_root = root.resolve()
    path = (resolved_root / relative).resolve()
    return path if resolved_root in path.parents else None


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
