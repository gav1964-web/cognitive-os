"""End-to-end field trial for the no-safe-candidate recovery loop."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contract_registry import ContractRegistry
from .programmer_patch_synthesizer import synthesize_recovery_patch_package
from .role_chain_interaction import build_role_chain_trace
from .role_pipeline import run_role_pipeline
from .recovery_patch_verification import verify_recovery_patch_package
from .recovery_patch_admission import build_recovery_patch_admission


def run_no_safe_candidate_recovery_field_trial(
    root: Path,
    *,
    project_dir: Path,
    write: bool = False,
) -> dict[str, Any]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    execution_dir = root / "artifacts" / "field_trials" / f"no_safe_candidate_recovery_{stamp}"
    source_path = project_dir / "legacy.py"
    before_hash = _sha256(source_path)
    before = run_role_pipeline(
        root=root,
        project_dir=project_dir,
        goal=f"Assess recovery entry for {project_dir.name}",
        write=False,
    )
    recovery = dict(before.get("no_safe_candidate_recovery") or {})
    package = synthesize_recovery_patch_package(
        execution_dir=execution_dir,
        project_dir=project_dir,
        recovery_route=recovery,
    )
    differential = (
        verify_recovery_patch_package(
            project_dir=project_dir,
            patch_package=package,
            verification_dir=execution_dir / "differential_verification",
        )
        if package.get("status") == "prepared"
        else {}
    )
    if differential:
        package["differential_verification"] = differential
        package["verification"]["tester_differential_status"] = differential.get("status")
    sandbox_text = str(package.get("sandbox_project") or "")
    after = (
        run_role_pipeline(
            root=root,
            project_dir=Path(sandbox_text),
            goal=f"Verify recovery candidate for {project_dir.name}",
            write=False,
        )
        if package.get("status") == "prepared" and sandbox_text
        else {}
    )
    admission = build_recovery_patch_admission(
        patch_package=package,
        architect_result=after,
    )
    candidate = str(dict(recovery.get("provisional_candidate") or {}).get("candidate") or "")
    checks = {
        "before_is_controlled_stop": before.get("next_action") == "rework_role_artifacts",
        "researcher_candidate_is_bounded": recovery.get("status") == "bounded_rework_ready",
        "architect_did_not_replace_stop_early": dict(recovery.get("architect_reentry_gate") or {}).get(
            "can_replace_controlled_stop"
        )
        is False,
        "developer_patch_prepared": package.get("status") == "prepared",
        "tester_differential_passed": differential.get("status") == "passed",
        "patch_is_sandbox_only": package.get("source_code_changes") is False
        and dict(package.get("policy") or {}).get("apply_source_enabled") is False,
        "original_source_unchanged": before_hash == _sha256(source_path),
        "normal_architect_gate_selected_candidate": dict(after.get("role_quality") or {}).get(
            "selected_extraction_candidate"
        )
        == candidate,
        "handoff_reached_implementer": dict(after.get("role_quality") or {}).get("implementation_target")
        == candidate,
        "recovery_not_needed_after_patch": dict(after.get("no_safe_candidate_recovery") or {}).get("status")
        == "not_applicable",
        "admission_waits_for_human_approval": admission.get("status") == "ready_for_human_approval"
        and admission.get("automatic_apply") is False,
    }
    report = {
        "artifact_type": "NoSafeCandidateRecoveryFieldTrialReport",
        "schema_version": "no_safe_candidate_recovery_field_trial.v1",
        "status": "ok" if all(checks.values()) else "failed",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project": project_dir.name,
        "candidate": candidate,
        "checks": checks,
        "before": {
            "next_action": before.get("next_action"),
            "recommendation": before.get("recommendation"),
            "role_chain": build_role_chain_trace(project=project_dir.name, result=before),
        },
        "developer": {
            "patch_status": package.get("status"),
            "patch_reason": package.get("reason"),
            "patches": list(package.get("patches") or []),
            "sandbox_project": package.get("sandbox_project"),
            "differential_verification": differential,
        },
        "after": {
            "next_action": after.get("next_action"),
            "recommendation": after.get("recommendation"),
            "selected_target": dict(after.get("role_quality") or {}).get("selected_extraction_candidate"),
            "role_chain": build_role_chain_trace(project=f"{project_dir.name}_recovered", result=after)
            if after
            else None,
        },
        "admission": admission,
        "safety": {
            "original_source_changes": before_hash != _sha256(source_path),
            "registry_changes": False,
            "automatic_apply": False,
        },
    }
    registry = ContractRegistry({})
    registry.validate_artifact(package)
    registry.validate_artifact(admission)
    registry.validate_artifact(report)
    if write:
        execution_dir.mkdir(parents=True, exist_ok=True)
        package_path = execution_dir / "recovery_patch_package.json"
        admission_path = execution_dir / "recovery_patch_admission.json"
        report_path = execution_dir / "report.json"
        package_path.write_text(
            json.dumps(package, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        admission_path.write_text(
            json.dumps(admission, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        report["package_path"] = package_path.as_posix()
        report["admission_path"] = admission_path.as_posix()
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        report["report_path"] = report_path.as_posix()
    return report


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
