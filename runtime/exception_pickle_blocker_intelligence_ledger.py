"""Ledger and active-attempt readers for exception-pickle blocker intelligence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _latest_blocked_rows_by_target(ledger: dict[str, Any]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in ledger.get("blocked_cases") or []:
        if not isinstance(row, dict):
            continue
        key = f"{row.get('project')}::{row.get('target')}"
        latest[key] = dict(row)
    return latest


def _latest_active_attempt_details_by_target(root: Path) -> dict[str, dict[str, Any]]:
    details: dict[str, dict[str, Any]] = {}
    report_dir = root / "artifacts" / "project_development"
    if not report_dir.is_dir():
        return details
    for path in sorted(report_dir.glob("exception_pickle_active_application_*.json")):
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(report, dict):
            continue
        generated_at = str(report.get("generated_at") or path.name)
        for attempt in report.get("attempts") or []:
            if not isinstance(attempt, dict):
                continue
            candidate = dict(attempt.get("candidate") or {})
            key = f"{candidate.get('project')}::{candidate.get('target')}"
            if key == "None::None":
                continue
            current = details.get(key)
            if current and str(current.get("_generated_at") or "") > generated_at:
                continue
            enriched = dict(attempt)
            enriched["_generated_at"] = generated_at
            enriched["_report_path"] = path.as_posix()
            details[key] = enriched
    return details


def _semantic_replay_error(blocked: dict[str, Any]) -> str:
    replay = blocked.get("project_native_semantic_replay")
    if isinstance(replay, dict):
        return str(replay.get("stderr") or replay.get("stdout") or "")
    return ""
