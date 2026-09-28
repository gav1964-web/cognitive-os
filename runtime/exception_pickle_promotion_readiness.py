"""Promotion-readiness gate for exception pickle reconstruction transfers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_LEDGER = Path("artifacts/project_development/supervised_exception_pickle_transfer_ledger.json")
DEFAULT_AUDIT = Path("artifacts/project_development/exception_pickle_candidate_audit_20260831T120556188729Z.json")


def evaluate_exception_pickle_promotion_readiness(
    *,
    root: Path,
    ledger_path: Path = DEFAULT_LEDGER,
    audit_path: Path | None = DEFAULT_AUDIT,
    require_autonomous_evidence: bool = False,
) -> dict[str, Any]:
    """Evaluate whether supervised transfers justify a promotion-review request."""
    root = root.resolve()
    ledger = _read_json(root, ledger_path)
    cases = [dict(row) for row in ledger.get("cases") or [] if isinstance(row, dict)]
    autonomous_cases = [
        dict(row) for row in ledger.get("autonomous_cases") or [] if isinstance(row, dict)
    ]
    reports = [_case_report(root, row) for row in cases]
    autonomous_reports = [
        _autonomous_case_report(root, row, supervised_projects={
            str(case.get("project") or "") for case in cases if case.get("project")
        })
        for row in autonomous_cases
    ]
    audit = _read_json(root, audit_path) if audit_path is not None else {}
    verified_reports = [row for row in reports if row["verified"]]
    verified_autonomous_reports = [row for row in autonomous_reports if row["verified"]]
    project_names = {str(row.get("project") or "") for row in cases if row.get("project")}
    target_names = {str(row.get("target") or "") for row in cases if row.get("target")}
    autonomous_count = int(ledger.get("autonomous_verified_count") or 0)
    checks = {
        "ledger_threshold_met": ledger.get("status") == "threshold_met",
        "minimum_supervised_verified": int(ledger.get("verified_count") or 0)
        >= int(ledger.get("target_count") or 3),
        "minimum_independent_projects": len(project_names) >= 3,
        "minimum_distinct_targets": len(target_names) >= 3,
        "all_reports_verified": len(verified_reports) == len(cases) and bool(cases),
        "all_reports_semantic_verified": all(row["semantic_verified"] for row in reports),
        "all_reports_native_verified": all(row["native_verified"] for row in reports),
        "all_reports_stub_clean": all(row["stub_clean"] for row in reports),
        "all_reports_source_unchanged": all(row["source_unchanged"] for row in reports),
        "source_apply_forbidden": dict(ledger.get("safety") or {}).get("source_apply") is False
        and all(row["source_apply"] is False for row in reports),
        "kb_promotion_forbidden": dict(ledger.get("safety") or {}).get("kb_promotion") is False
        and all(row["memory_promotion"] is False for row in reports),
        "untouched_holdout_not_used": dict(ledger.get("safety") or {}).get("untouched_holdout_used") is False
        and dict(audit.get("scan") or {}).get("untouched_holdout_scanned") is False,
        "audit_available": audit.get("artifact_type") == "ExceptionPickleCandidateAudit",
        "autonomous_evidence_available": autonomous_count >= 1
        and len(verified_autonomous_reports) >= 1
        and autonomous_count == len(verified_autonomous_reports),
    }
    supervised_ready = all(
        checks[name]
        for name in (
            "ledger_threshold_met",
            "minimum_supervised_verified",
            "minimum_independent_projects",
            "minimum_distinct_targets",
            "all_reports_verified",
            "all_reports_semantic_verified",
            "all_reports_native_verified",
            "all_reports_stub_clean",
            "all_reports_source_unchanged",
            "source_apply_forbidden",
            "kb_promotion_forbidden",
            "untouched_holdout_not_used",
            "audit_available",
        )
    )
    autonomous_ready = checks["autonomous_evidence_available"]
    return {
        "artifact_type": "ExceptionPicklePromotionReadiness",
        "schema_version": "exception_pickle_promotion_readiness.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": (
            "eligible_for_promotion_review"
            if supervised_ready and (autonomous_ready or not require_autonomous_evidence)
            else "blocked"
        ),
        "promotion_review_allowed": supervised_ready,
        "kb_promotion_allowed": False,
        "autonomous_activation_allowed": supervised_ready and autonomous_ready and require_autonomous_evidence,
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "evidence": {
            "ledger": _relative(root, ledger_path),
            "audit": _relative(root, audit_path) if audit_path is not None else None,
            "projects": sorted(project_names),
            "targets": sorted(target_names),
            "reports": reports,
            "autonomous_reports": autonomous_reports,
            "supervised_verified_count": int(ledger.get("verified_count") or 0),
            "autonomous_verified_count": autonomous_count,
        },
        "next_gates": _next_gates(autonomous_ready),
    }


def _autonomous_case_report(
    root: Path, case: dict[str, Any], *, supervised_projects: set[str]
) -> dict[str, Any]:
    report_path = Path(str(case.get("report") or ""))
    payload = _read_json(root, report_path) if report_path else {}
    checks = dict(payload.get("checks") or {})
    project = str(case.get("project") or "")
    target = str(case.get("target") or "")
    replay = dict(payload.get("project_native_semantic_replay") or {})
    verified = all((
        payload.get("artifact_type") == "ExceptionPickleAutonomousShadowRun",
        payload.get("status") == "autonomous_verified_shadow",
        payload.get("counts_as_autonomous_verified_transformation") is True,
        replay.get("status") == "passed",
        checks.get("project_native_semantic_replay") is True,
        not payload.get("failed_checks"),
        payload.get("source_apply") is False,
        payload.get("kb_promotion") is False,
        bool(project),
        bool(target),
        project not in supervised_projects,
    ))
    return {
        "project": project,
        "target": target,
        "report": _relative(root, report_path),
        "verified": verified,
        "status": payload.get("status"),
        "semantic_replay_status": replay.get("status"),
        "source_apply": payload.get("source_apply"),
        "kb_promotion": payload.get("kb_promotion"),
    }


def _next_gates(autonomous_ready: bool) -> list[str]:
    gates = [
        "external_architect_review",
        "independent_holdout_transaction",
        "independent_evaluator_review",
    ]
    if not autonomous_ready:
        gates.append("autonomous_shadow_run_before_activation")
    gates.append("kb_promotion_transaction_requires_manual_authorization")
    return gates


def _case_report(root: Path, case: dict[str, Any]) -> dict[str, Any]:
    report_path = Path(str(case.get("report") or ""))
    payload = _read_json(root, report_path) if report_path else {}
    result = dict(payload.get("implementation_result") or {})
    native = dict(result.get("project_native_verification") or {})
    semantic = dict(result.get("semantic_verification") or {})
    semantic_status = semantic.get("status")
    targeted = dict(native.get("targeted_replay") or {})
    test_targets = [str(item) for item in targeted.get("test_targets") or []]
    native_verified = native.get("status") == "passed" and targeted.get("status") == "passed" and dict(
        native.get("regression_suite") or {}
    ).get("status") == "passed"
    legacy_pickle_replay = native_verified and any("pickle" in target for target in test_targets)
    semantic_verified = semantic_status in {"passed", "not_required"} or legacy_pickle_replay
    return {
        "project": case.get("project"),
        "target": case.get("target"),
        "report": _relative(root, report_path),
        "verified": result.get("status") == "verified_in_sandbox",
        "semantic_verified": semantic_verified,
        "semantic_basis": (
            str(semantic_status)
            if semantic_status in {"passed", "not_required"}
            else "legacy_pickle_native_replay" if legacy_pickle_replay else "missing"
        ),
        "native_verified": native_verified,
        "stub_clean": dict(result.get("stub_admission") or {}).get("status") == "passed",
        "source_unchanged": dict(result.get("source_invariant") or {}).get("unchanged") is True,
        "source_apply": result.get("source_apply"),
        "memory_promotion": result.get("memory_promotion"),
    }


def _read_json(root: Path, path: Path) -> dict[str, Any]:
    resolved = path if path.is_absolute() else root / path
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact must be an object: {resolved}")
    return payload


def _relative(root: Path, path: Path) -> str:
    resolved = path if path.is_absolute() else root / path
    return resolved.resolve().relative_to(root).as_posix()
