"""Aggregate narrow-role semantic evidence across project cases."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable


def stratum_check(cases: list[dict[str, Any]], stratum: str) -> dict[str, Any]:
    selected = [row for row in cases if row.get("project_stratum") == stratum]
    enough_cases = len(selected) >= 2
    return {
        "case_count": len(selected),
        "source_lineage_count": len({row.get("source_lineage") for row in selected if row.get("source_lineage")}),
        "source_owner_count": len({row.get("source_owner") for row in selected if row.get("source_owner")}),
        "projects": sorted(str(row.get("project")) for row in selected),
        "status": "passed" if enough_cases and all(row.get("status") == "passed" for row in selected) else "evidence_required",
    }


def worst_role_scores(
    cases: list[dict[str, Any]], roles: Iterable[str]
) -> dict[str, float | None]:
    return {
        role: min(
            (
                float(dict(row.get("role_scores") or {})[role])
                for row in cases
                if role in dict(row.get("role_scores") or {})
            ),
            default=None,
        )
        for role in roles
    }


def digest_evidence(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
