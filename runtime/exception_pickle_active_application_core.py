"""Core helpers for active exception-pickle application."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

def _recipe(
    active_catalog: dict[str, Any],
    required: list[str],
    *,
    root: Path,
    row: dict[str, Any] | None = None,
) -> dict[str, Any]:
    operator = dict(active_catalog.get("operator") or {})
    return {
        "operator_id": operator.get("id"),
        "reconstruction_method": operator.get("reconstruction_method"),
        "state_strategy": operator.get("state_strategy"),
        "required_constructor_inputs": required,
        "allow_keyword_only_state_reducer": bool(
            dict(row or {}).get("formatted_super_argument")
            or _candidate_requires_keyword_only_state_reducer(root, row or {})
        ),
    }


def _candidate_requires_keyword_only_state_reducer(root: Path, row: dict[str, Any]) -> bool:
    required = {str(value) for value in row.get("required_constructor_parameters") or []}
    if not required:
        return False
    source_file = root / str(row.get("project_root") or "") / str(row.get("path") or "")
    if not source_file.is_file():
        return False
    try:
        source = source_file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        source = source_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    class_name = str(row.get("class_name") or "")
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        constructor = next(
            (
                item
                for item in node.body
                if isinstance(item, ast.FunctionDef) and item.name == "__init__"
            ),
            None,
        )
        if constructor is None:
            return False
        keyword_only = {item.arg for item in constructor.args.kwonlyargs}
        return bool(required & keyword_only)
    return False


def _object_contracts_for_candidate(
    candidate: dict[str, Any], admitted_object_contracts: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    key = f"{candidate.get('project')}::{candidate.get('target')}"
    row = dict(admitted_object_contracts.get(key) or {})
    return {
        str(item.get("parameter")): dict(item)
        for item in row.get("contracts") or []
        if isinstance(item, dict) and item.get("parameter")
    }


def _attempt_result(
    status: str,
    candidate: dict[str, Any],
    checks: dict[str, bool],
    *,
    blocker_kind: str | None = None,
    sandbox: Path | None = None,
) -> dict[str, Any]:
    if blocker_kind is None:
        from .exception_pickle_active_application_replay_policy import _classify_blocker

        blocker_kind = _classify_blocker(status, checks, None)
    return {
        "artifact_type": "ExceptionPickleActiveApplicationAttempt",
        "status": status,
        "candidate": candidate,
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "blocker_kind": blocker_kind,
        "sandbox_project": sandbox.as_posix() if sandbox else None,
        "source_apply": False,
        "kb_promotion": False,
    }

def _write_application_ledger(
    root: Path,
    path: Path,
    transfer_ledger: dict[str, Any],
    application_ledger: dict[str, Any],
    report: dict[str, Any],
) -> None:
    from .exception_pickle_active_application_replay_policy import _blocker_summary

    resolved = path if path.is_absolute() else root / path
    resolved.parent.mkdir(parents=True, exist_ok=True)
    cases = [dict(row) for row in application_ledger.get("cases") or [] if isinstance(row, dict)]
    blocked_cases = [
        dict(row) for row in application_ledger.get("blocked_cases") or [] if isinstance(row, dict)
    ]
    selected_rows = [
        dict(row)
        for row in report.get("selected_applications") or []
        if isinstance(row, dict)
    ]
    if not selected_rows and report.get("selected_application"):
        selected_rows = [dict(report.get("selected_application") or {})]
    for selected in selected_rows:
        candidate = dict(selected.get("candidate") or {})
        cases.append({
            "project": candidate.get("project"),
            "target": candidate.get("target"),
            "status": selected.get("status"),
            "generated_at": report.get("generated_at"),
        })
    for attempt in report.get("attempts") or []:
        attempt_row = dict(attempt)
        if attempt_row.get("status") == "applied_active_kb":
            continue
        candidate = dict(attempt_row.get("candidate") or {})
        blocked_cases.append({
            "project": candidate.get("project"),
            "target": candidate.get("target"),
            "status": attempt_row.get("status"),
            "blocker_kind": attempt_row.get("blocker_kind"),
            "failed_checks": list(attempt_row.get("failed_checks") or []),
            "generated_at": report.get("generated_at"),
        })
    ledger = {
        "artifact_type": "ExceptionPickleActiveApplicationLedger",
        "schema_version": "exception_pickle_active_application_ledger.v1",
        "updated_at": report.get("generated_at"),
        "active_pattern": "preserve_exception_constructor_reconstruction",
        "supervised_verified_count": int(transfer_ledger.get("verified_count") or 0),
        "autonomous_verified_count": int(transfer_ledger.get("autonomous_verified_count") or 0),
        "active_pattern_applied_count": len([
            row for row in cases if row.get("status") == "applied_active_kb"
        ]),
        "active_pattern_blocked_count": len(blocked_cases),
        "blocker_summary": _blocker_summary(blocked_cases),
        "cases": cases,
        "blocked_cases": blocked_cases,
        "source_apply": False,
        "kb_promotion": False,
    }
    resolved.write_text(json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

def _read_json(root: Path, path: Path) -> dict[str, Any]:
    resolved = path if path.is_absolute() else root / path
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact must be an object: {resolved}")
    return payload


def _read_optional_json(root: Path, path: Path) -> dict[str, Any]:
    resolved = path if path.is_absolute() else root / path
    if not resolved.exists():
        return {}
    return _read_json(root, path)
