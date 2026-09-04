"""Read-only holdout transaction for exception pickle reconstruction promotion."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .exception_pickle_promotion_readiness import (
    evaluate_exception_pickle_promotion_readiness,
)


DEFAULT_LEDGER = Path("artifacts/project_development/supervised_exception_pickle_transfer_ledger.json")
DEFAULT_AUDIT = Path("artifacts/project_development/exception_pickle_candidate_audit_20260831T120556188729Z.json")


def run_exception_pickle_holdout_transaction(
    *,
    root: Path,
    ledger_path: Path = DEFAULT_LEDGER,
    audit_path: Path = DEFAULT_AUDIT,
    minimum_holdout_candidates: int = 3,
    regression_passed: bool = False,
    config_doctor_passed: bool = False,
) -> dict[str, Any]:
    """Check promotion prerequisites without applying KB or source changes."""
    root = root.resolve()
    readiness = evaluate_exception_pickle_promotion_readiness(
        root=root,
        ledger_path=ledger_path,
        audit_path=audit_path,
    )
    audit = _read_json(root, audit_path)
    supervised_projects = set(readiness["evidence"]["projects"])
    holdouts = [
        _candidate_summary(row)
        for row in audit.get("candidates") or []
        if _is_applicable_holdout(row, supervised_projects, root=root)
    ]
    projects = {row["project"] for row in holdouts}
    checks = {
        "promotion_review_is_ready": readiness.get("promotion_review_allowed") is True,
        "minimum_holdout_candidates": len(holdouts) >= minimum_holdout_candidates,
        "minimum_holdout_projects": len(projects) >= minimum_holdout_candidates,
        "regression_tests": regression_passed,
        "config_doctor": config_doctor_passed,
        "source_apply_forbidden": True,
        "kb_promotion_not_applied": True,
        "autonomous_activation_forbidden": readiness.get("autonomous_activation_allowed") is False,
    }
    return {
        "artifact_type": "ExceptionPickleHoldoutTransaction",
        "schema_version": "exception_pickle_holdout_transaction.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "holdout_ready" if all(checks.values()) else "blocked",
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "readiness_status": readiness.get("status"),
        "holdout_candidates": holdouts[:25],
        "holdout_candidate_count": len(holdouts),
        "holdout_project_count": len(projects),
        "minimum_holdout_candidates": minimum_holdout_candidates,
        "source_apply": False,
        "kb_promotion": False,
        "autonomous_activation": False,
    }


def _is_applicable_holdout(
    row: dict[str, Any], supervised_projects: set[str], *, root: Path
) -> bool:
    required = [str(item) for item in row.get("required_constructor_parameters") or []]
    stored = {str(item) for item in row.get("stored_constructor_parameters") or []}
    project = str(row.get("canonical_project") or row.get("project") or "")
    project_root = root / str(row.get("project_root") or "")
    return all((
        project not in supervised_projects,
        bool(project),
        bool(required),
        len(required) <= 4,
        set(required) <= stored,
        project_root.exists(),
    ))


def _candidate_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "project": row.get("canonical_project") or row.get("project"),
        "target": f"{row.get('path')}:{row.get('class_name')}.__init__",
        "score": row.get("score"),
        "required_constructor_parameters": list(row.get("required_constructor_parameters") or []),
        "stored_constructor_parameters": list(row.get("stored_constructor_parameters") or []),
        "pickle_test_signals": list(row.get("pickle_test_signals") or []),
    }


def _read_json(root: Path, path: Path) -> dict[str, Any]:
    resolved = path if path.is_absolute() else root / path
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact must be an object: {resolved}")
    return payload
