"""Config-backed contract transform operator catalog."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "config" / "contract_transform_operators.json"


def load_contract_transform_operators(path: str | Path | None = None) -> dict[str, Any]:
    source = Path(path or DEFAULT_PATH)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "contract_transform_operators.v1":
        raise ValueError("Unsupported contract transform operators schema")
    if dict(payload.get("admission_policy") or {}).get("automatic_source_mutation_allowed") is not False:
        raise ValueError("Contract transform operators cannot allow automatic source mutation")
    return payload


def operator_records(recipe: dict[str, Any], catalog: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    payload = catalog or load_contract_transform_operators()
    allowed = [str(item) for item in list(recipe.get("allowed_transforms") or [])]
    by_id = {str(row.get("id") or ""): dict(row) for row in list(payload.get("operators") or []) if isinstance(row, dict)}
    return [by_id[operator_id] for operator_id in allowed if operator_id in by_id]
