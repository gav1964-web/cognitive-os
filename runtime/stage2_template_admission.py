"""Admission gate for deterministic Stage 2 package templates."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .greenfield_scaffold import create_greenfield_scaffold
from .greenfield_stage2_templates import has_case
from .programmer_project_review import review_programmer_project


def run_stage2_template_admission(*, root: Path, curriculum_dir: Path, case_name: str, write: bool = False) -> dict[str, Any]:
    reference_path = curriculum_dir / case_name / "teacher_reference.json"
    if not reference_path.is_file():
        return _blocked(case_name, ["teacher_reference_missing"], write=write, root=root)
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    blockers = _reference_blockers(reference)
    if not has_case(case_name):
        blockers.append("deterministic_template_missing")
    if blockers:
        return _blocked(case_name, blockers, write=write, root=root)
    scaffold = create_greenfield_scaffold(root=root, case_name=case_name, reference=reference)
    review = review_programmer_project(scaffold=scaffold, reference=reference)
    missing_acceptance = list(dict(review.get("coverage", {})).get("missing_acceptance", []))
    checks = dict(review.get("checks", {}))
    failed_checks = [key for key, passed in checks.items() if not passed]
    status = "admitted" if review.get("recommendation") in {"approve", "approve_with_risks"} and not missing_acceptance and not failed_checks else "blocked"
    result = {
        "artifact_type": "Stage2TemplateAdmissionResult",
        "status": status,
        "created_at": _now(),
        "case": case_name,
        "template_available": True,
        "reference_quality": reference.get("reference_quality"),
        "scaffold": {
            "project_dir": scaffold.get("project_dir"),
            "verification": scaffold.get("verification"),
            "acceptance_covered": scaffold.get("acceptance_covered"),
        },
        "tester_review": review,
        "blockers": missing_acceptance + failed_checks,
        "invariants": _invariants(),
    }
    if write:
        result["report_path"] = _write_report(root, result).as_posix()
    return result


def _reference_blockers(reference: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if reference.get("reference_quality") != "teacher_reference_not_ground_truth":
        blockers.append("reference_quality_not_teacher_reference")
    if not reference.get("prompt"):
        blockers.append("prompt_missing")
    if not reference.get("expected_artifacts"):
        blockers.append("expected_artifacts_missing")
    if not reference.get("acceptance_criteria"):
        blockers.append("acceptance_criteria_missing")
    return blockers


def _blocked(case_name: str, blockers: list[str], *, write: bool, root: Path) -> dict[str, Any]:
    result = {
        "artifact_type": "Stage2TemplateAdmissionResult",
        "status": "blocked",
        "created_at": _now(),
        "case": case_name,
        "template_available": False,
        "blockers": blockers,
        "invariants": _invariants(),
    }
    if write:
        result["report_path"] = _write_report(root, result).as_posix()
    return result


def _invariants() -> dict[str, bool]:
    return {
        "source_tree_changes": False,
        "registry_changes": False,
        "teacher_reference_is_ground_truth": False,
        "admission_does_not_promote_runtime": True,
    }


def _write_report(root: Path, report: dict[str, Any]) -> Path:
    out_dir = root / "artifacts" / "stage2_template_admission"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = out_dir / f"{report['case']}_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
