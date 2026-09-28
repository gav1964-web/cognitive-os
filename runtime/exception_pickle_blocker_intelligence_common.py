"""Shared helpers for exception-pickle blocker intelligence."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


def _top(counter: Counter[str], limit: int) -> list[dict[str, Any]]:
    return [
        {"value": value, "count": count}
        for value, count in counter.most_common(limit)
    ]


def _object_contracts_for_sample(entry: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not entry:
        return {}
    return {
        str(contract.get("parameter")): dict(contract)
        for contract in entry.get("contracts") or []
        if isinstance(contract, dict) and contract.get("parameter")
    }


def _candidate_key(row: dict[str, Any]) -> str:
    project = row.get("canonical_project") or row.get("project")
    target = f"{row.get('path')}:{row.get('class_name')}.__init__"
    return f"{project}::{target}"


def _read_json(root: Path, path: Path) -> dict[str, Any]:
    resolved = path if path.is_absolute() else root / path
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact must be an object: {resolved}")
    return payload
