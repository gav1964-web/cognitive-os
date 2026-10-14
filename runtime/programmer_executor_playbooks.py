"""Config-backed playbooks for Programmer Executor decisions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "config" / "programmer_executor_playbooks.json"


def load_programmer_executor_playbooks(path: str | Path | None = None) -> dict[str, Any]:
    source = Path(path or DEFAULT_PATH)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "programmer_executor_playbooks.v1":
        raise ValueError("Unsupported programmer executor playbooks schema")
    return payload


def select_executor_playbooks(acceptance_summary: dict[str, Any] | None) -> list[dict[str, Any]]:
    policy = load_programmer_executor_playbooks()
    acceptance = dict(acceptance_summary or {})
    reasons = dict(acceptance.get("skipped_reason_counts") or {})
    matches: list[dict[str, Any]] = []
    for row in policy.get("playbooks", []):
        playbook = dict(row)
        matcher = dict(playbook.get("match") or {})
        if _matches(matcher, acceptance, reasons):
            matches.append(_public_playbook(playbook))
    return matches


def _matches(matcher: dict[str, Any], acceptance: dict[str, Any], reasons: dict[str, Any]) -> bool:
    signal = str(matcher.get("acceptance_signal") or "")
    if signal and str(acceptance.get("signal_strength") or "") != signal:
        return False
    reason = str(matcher.get("skipped_reason") or "")
    if reason and int(reasons.get(reason) or 0) <= 0:
        return False
    return bool(signal or reason)


def _public_playbook(playbook: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(playbook.get("id") or ""),
        "label": str(playbook.get("label") or ""),
        "action": str(playbook.get("action") or ""),
        "safe_next_step": str(playbook.get("safe_next_step") or ""),
        "required_gates": [str(item) for item in list(playbook.get("required_gates") or [])],
        "confidence": float(playbook.get("confidence") or 0.0),
        "authority": "advisory_playbook_only",
    }
