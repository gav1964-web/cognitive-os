"""Turn SystemKnowledgeIR losses into role-owned improvement backlog."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY_PATH = ROOT / "config" / "system_knowledge_ir_backlog_policy.json"


@lru_cache(maxsize=8)
def load_ir_backlog_policy(path: str | None = None) -> dict[str, Any]:
    source = Path(path).resolve() if path else DEFAULT_POLICY_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "system_knowledge_ir_backlog_policy.v1" or payload.get("status") != "active":
        raise ValueError("IR backlog policy must use active system_knowledge_ir_backlog_policy.v1")
    categories = payload.get("categories")
    if not isinstance(categories, dict) or not categories:
        raise ValueError("IR backlog policy requires categories")
    for category, row in categories.items():
        if not isinstance(row, dict) or not all(row.get(field) for field in ("role", "severity", "suggested_work")):
            raise ValueError(f"IR backlog policy category is incomplete: {category}")
        if row["severity"] not in {"high", "medium", "low"}:
            raise ValueError(f"IR backlog policy severity is invalid: {category}")
    return payload


_POLICY = load_ir_backlog_policy()
_CATEGORIES = {str(key): dict(value) for key, value in dict(_POLICY["categories"]).items()}
ROLE_BY_CATEGORY = {key: str(value["role"]) for key, value in _CATEGORIES.items()}
ACTION_BY_CATEGORY = {key: str(value["suggested_work"]) for key, value in _CATEGORIES.items()}
SEVERITY_BY_CATEGORY = {key: str(value["severity"]) for key, value in _CATEGORIES.items()}


def build_ir_loss_backlog(diff: dict[str, Any]) -> list[dict[str, Any]]:
    """Create deterministic role backlog items from a SystemKnowledgeIRDiff."""

    items = []
    for loss in list(diff.get("losses", []) or []):
        category = str(loss.get("category") or "unknown")
        missing = [str(item) for item in list(loss.get("missing") or []) if item]
        if not missing:
            continue
        items.append(
            {
                "artifact_type": "IRLossBacklogItem",
                "id": _item_id(category, missing),
                "status": "open",
                "role": ROLE_BY_CATEGORY.get(category, "compiler"),
                "category": category,
                "severity": SEVERITY_BY_CATEGORY.get(category, "medium"),
                "missing": missing[:12],
                "suggested_work": ACTION_BY_CATEGORY.get(category, "preserve lost IR evidence in compiler output"),
                "evidence": {
                    "diff_artifact_type": diff.get("artifact_type"),
                    "diff_score": diff.get("score"),
                },
            }
        )
    return _sort_items(items)


def summarize_ir_loss_backlog(items: list[dict[str, Any]]) -> dict[str, Any]:
    by_role: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    for item in items:
        by_role[str(item.get("role") or "unknown")] = by_role.get(str(item.get("role") or "unknown"), 0) + 1
        severity = str(item.get("severity") or "medium")
        by_severity[severity] = by_severity.get(severity, 0) + 1
    return {
        "items": len(items),
        "by_role": dict(sorted(by_role.items())),
        "by_severity": dict(sorted(by_severity.items())),
        "top_roles": [role for role, _ in sorted(by_role.items(), key=lambda row: (-row[1], row[0]))[:4]],
    }


def _item_id(category: str, missing: list[str]) -> str:
    head = missing[0] if missing else "unknown"
    safe = "".join(ch.lower() if ch.isalnum() else "_" for ch in f"{category}_{head}")
    return "ir_loss_" + "_".join(part for part in safe.split("_") if part)[:80]


def _sort_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rank = {"high": 0, "medium": 1, "low": 2}
    return sorted(items, key=lambda item: (rank.get(str(item.get("severity")), 1), str(item.get("role")), str(item.get("id"))))
