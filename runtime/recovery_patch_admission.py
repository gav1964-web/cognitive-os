"""Human-bound admission, atomic apply, and rollback for recovery patches."""

from __future__ import annotations

import hashlib
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def build_recovery_patch_admission(
    *,
    patch_package: dict[str, Any],
    architect_result: dict[str, Any],
) -> dict[str, Any]:
    patches = [dict(row) for row in patch_package.get("patches", []) if isinstance(row, dict)]
    candidate = str(patches[0].get("created_target") or "") if len(patches) == 1 else ""
    quality = dict(architect_result.get("role_quality") or {})
    differential = dict(patch_package.get("differential_verification") or {})
    checks = {
        "single_bounded_patch": len(patches) == 1,
        "developer_patch_prepared": patch_package.get("status") == "prepared",
        "tester_differential_passed": differential.get("status") == "passed",
        "patch_digest_bound": bool(patch_package.get("patch_digest")),
        "source_precondition_bound": bool(patch_package.get("source_precondition_sha256")),
        "architect_selected_created_target": bool(candidate)
        and quality.get("selected_extraction_candidate") == candidate,
        "implementer_handoff_preserved": bool(candidate) and quality.get("implementation_target") == candidate,
        "reviewer_approved_recovered_route": architect_result.get("recommendation")
        in {"approve", "approve_with_risks"},
        "automatic_apply_disabled": dict(patch_package.get("policy") or {}).get("apply_source_enabled")
        is False,
    }
    ready = all(checks.values())
    return {
        "artifact_type": "RecoveryPatchAdmission",
        "status": "ready_for_human_approval" if ready else "blocked",
        "created_at": _now(),
        "candidate": candidate,
        "patch_digest": patch_package.get("patch_digest"),
        "source_precondition_sha256": patch_package.get("source_precondition_sha256"),
        "checks": checks,
        "required_approval": {
            "approved": True,
            "decision": "approve_apply",
            "approver": "non_empty_human_identity",
            "patch_digest": patch_package.get("patch_digest"),
        },
        "automatic_apply": False,
        "rollback_required": True,
    }


def apply_recovery_patch(
    *,
    project_dir: Path,
    patch_package: dict[str, Any],
    admission: dict[str, Any],
    approval: dict[str, Any] | None,
) -> dict[str, Any]:
    reason = _approval_block_reason(patch_package, admission, approval)
    if reason:
        return _apply_receipt(status="blocked", reason=reason, patch_package=patch_package)
    patch = dict(list(patch_package.get("patches") or [])[0])
    relative = str(patch.get("file") or "")
    sandbox = Path(str(patch_package.get("sandbox_project") or ""))
    target = _scoped_file(project_dir, relative)
    patched_source = _scoped_file(sandbox, relative)
    if target is None or patched_source is None or not target.is_file() or not patched_source.is_file():
        return _apply_receipt(status="blocked", reason="apply_source_missing_or_outside_scope", patch_package=patch_package)
    before_hash = _sha256(target)
    if before_hash != patch_package.get("source_precondition_sha256"):
        return _apply_receipt(status="blocked", reason="source_precondition_mismatch", patch_package=patch_package)
    if _sha256(patched_source) != patch_package.get("patched_source_sha256"):
        return _apply_receipt(status="blocked", reason="sandbox_patch_digest_mismatch", patch_package=patch_package)
    execution_root = sandbox.parent.parent
    snapshot = execution_root / "source_snapshot" / relative
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(target, snapshot)
    temporary = target.with_name(f".{target.name}.recovery-apply.tmp")
    shutil.copy2(patched_source, temporary)
    os.replace(temporary, target)
    return {
        "artifact_type": "RecoveryPatchApplyReceipt",
        "status": "applied",
        "created_at": _now(),
        "project": project_dir.as_posix(),
        "file": relative,
        "patch_digest": patch_package.get("patch_digest"),
        "approver": dict(approval or {}).get("approver"),
        "source_precondition_sha256": before_hash,
        "applied_source_sha256": _sha256(target),
        "snapshot": snapshot.as_posix(),
        "rollback_available": True,
        "source_code_changes": True,
    }


def rollback_recovery_patch(*, project_dir: Path, receipt: dict[str, Any]) -> dict[str, Any]:
    if receipt.get("status") != "applied" or not receipt.get("rollback_available"):
        return {"artifact_type": "RecoveryPatchRollbackReceipt", "status": "blocked", "reason": "no_applied_patch_receipt"}
    target = _scoped_file(project_dir, str(receipt.get("file") or ""))
    snapshot = Path(str(receipt.get("snapshot") or ""))
    if target is None or not target.is_file() or not snapshot.is_file():
        return {"artifact_type": "RecoveryPatchRollbackReceipt", "status": "blocked", "reason": "rollback_source_missing"}
    if _sha256(target) != receipt.get("applied_source_sha256"):
        return {"artifact_type": "RecoveryPatchRollbackReceipt", "status": "blocked", "reason": "post_apply_source_drift"}
    temporary = target.with_name(f".{target.name}.recovery-rollback.tmp")
    shutil.copy2(snapshot, temporary)
    os.replace(temporary, target)
    restored = _sha256(target)
    return {
        "artifact_type": "RecoveryPatchRollbackReceipt",
        "status": "rolled_back",
        "created_at": _now(),
        "project": project_dir.as_posix(),
        "file": receipt.get("file"),
        "patch_digest": receipt.get("patch_digest"),
        "restored_source_sha256": restored,
        "matches_precondition": restored == receipt.get("source_precondition_sha256"),
        "source_code_changes": True,
    }


def _approval_block_reason(
    package: dict[str, Any], admission: dict[str, Any], approval: dict[str, Any] | None
) -> str | None:
    if admission.get("status") != "ready_for_human_approval":
        return "admission_not_ready"
    decision = dict(approval or {})
    if decision.get("approved") is not True or decision.get("decision") != "approve_apply":
        return "explicit_human_approval_required"
    if not str(decision.get("approver") or "").strip():
        return "human_approver_identity_required"
    digest = str(package.get("patch_digest") or "")
    if decision.get("patch_digest") != digest or admission.get("patch_digest") != digest:
        return "approval_patch_digest_mismatch"
    return None


def _apply_receipt(*, status: str, reason: str, patch_package: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_type": "RecoveryPatchApplyReceipt",
        "status": status,
        "created_at": _now(),
        "reason": reason,
        "patch_digest": patch_package.get("patch_digest"),
        "rollback_available": False,
        "source_code_changes": False,
    }


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
