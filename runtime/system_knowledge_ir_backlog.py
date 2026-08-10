"""Turn SystemKnowledgeIR losses into role-owned improvement backlog."""

from __future__ import annotations

from typing import Any


ROLE_BY_CATEGORY = {
    "purpose": "project_analyzer",
    "public_interfaces": "project_analyzer",
    "behavior_contracts": "spec_writer",
    "architecture_slices": "architect",
    "acceptance_tests": "spec_writer",
    "data_artifacts": "project_analyzer",
}

ACTION_BY_CATEGORY = {
    "purpose": "preserve project purpose in generated README and IR seed",
    "public_interfaces": "carry route/CLI/file interfaces from IR into generated source and docs",
    "behavior_contracts": "emit source-backed behavior contracts that generated project analysis can recover",
    "architecture_slices": "compile first-slice boundaries into generated module names or docs",
    "acceptance_tests": "materialize acceptance criteria as generated contract tests",
    "data_artifacts": "copy or summarize required data artifacts with traceable names",
}

SEVERITY_BY_CATEGORY = {
    "public_interfaces": "high",
    "behavior_contracts": "high",
    "acceptance_tests": "medium",
    "architecture_slices": "medium",
    "purpose": "medium",
    "data_artifacts": "low",
}


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
