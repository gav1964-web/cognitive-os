"""Conservative executable confirmation for foundation role handoffs."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .executable_acceptance import run_executable_acceptance
from .implementation_plan_builder import build_implementation_plan
from .test_plan_builder import build_test_plan


def collect_foundation_executable_evidence(
    *, root: Path, project_dir: Path, technical_spec: dict[str, Any]
) -> dict[str, Any]:
    eligibility = _eligibility(technical_spec)
    if eligibility["status"] != "eligible":
        return eligibility
    implementation_plan = build_implementation_plan(technical_spec=technical_spec)
    test_plan = build_test_plan(
        technical_spec=technical_spec,
        implementation_plan=implementation_plan,
    )
    obligations = list(dict(test_plan.get("executable_acceptance") or {}).get("obligations") or [])
    if not obligations:
        return {**eligibility, "status": "skipped", "reason": "no_executable_obligations"}
    acceptance = run_executable_acceptance(
        root=root,
        project_dir=project_dir,
        test_plan=test_plan,
        work_dir=_work_dir(root, project_dir, str(eligibility["target"])),
    )
    summary = dict(acceptance.get("summary") or {})
    signal = str(summary.get("signal_strength") or "") if acceptance.get("status") == "passed" else ""
    return {
        "status": str(acceptance.get("status") or "failed"),
        "target": eligibility["target"],
        "acceptance_signal": signal,
        "summary": summary,
        "result_path": acceptance.get("result_path"),
        "source_code_changes": acceptance.get("source_code_changes", False),
    }


def _eligibility(spec: dict[str, Any]) -> dict[str, Any]:
    contract = dict(spec.get("extraction_contract") or {})
    target = str(contract.get("candidate") or "")
    request = dict(spec.get("first_slice_reselection_request") or {})
    structural = dict(contract.get("structural_evidence") or {})
    effects = list(dict(contract.get("side_effects") or {}).get("declared") or [])
    reason = ""
    if spec.get("artifact_type") != "TechnicalSpec":
        reason = "technical_spec_missing"
    elif request.get("status") == "required":
        reason = "first_slice_reselection_required"
    elif not target or contract.get("status") == "blocked_no_safe_candidate":
        reason = "safe_target_missing"
    elif effects:
        reason = "side_effectful_target"
    elif structural.get("state_mutation") is True:
        reason = "state_mutating_target"
    return {
        "status": "skipped" if reason else "eligible",
        "reason": reason or None,
        "target": target or None,
        "acceptance_signal": "",
    }


def _work_dir(root: Path, project_dir: Path, target: str) -> Path:
    digest = hashlib.sha256(f"{project_dir.resolve()}:{target}".encode("utf-8")).hexdigest()[:12]
    return root / "artifacts" / "executable_acceptance" / "foundation" / f"{project_dir.name}-{digest}"
