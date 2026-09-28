"""Round-trip comparison for SystemKnowledgeIR artifacts."""

from __future__ import annotations

from typing import Any


def compare_system_knowledge_ir(source_ir: dict[str, Any], target_ir: dict[str, Any]) -> dict[str, Any]:
    """Compare source and generated knowledge artifacts by contract-bearing fields."""

    categories = [
        _compare_values("purpose", _purpose_tokens(source_ir), _purpose_tokens(target_ir), 0.15),
        _compare_values("public_interfaces", _interface_keys(source_ir), _interface_keys(target_ir), 0.30),
        _compare_values("behavior_contracts", _behavior_keys(source_ir), _behavior_keys(target_ir), 0.25),
        _compare_values("architecture_slices", _slice_keys(source_ir), _slice_keys(target_ir), 0.10),
        _compare_values("acceptance_tests", _acceptance_keys(source_ir), _acceptance_keys(target_ir), 0.15),
        _compare_values("data_artifacts", _data_keys(source_ir), _data_keys(target_ir), 0.05),
    ]
    weighted = sum(float(row["score"]) * float(row["weight"]) for row in categories)
    score = round(weighted / sum(float(row["weight"]) for row in categories), 3)
    losses = [
        {"category": row["category"], "missing": row["missing"]}
        for row in categories
        if row["missing"]
    ]
    return {
        "artifact_type": "SystemKnowledgeIRDiff",
        "status": "ok" if score >= 0.85 and not _critical_losses(losses) else "needs_work",
        "score": score,
        "categories": categories,
        "losses": losses,
        "summary": {
            "preserved_categories": sum(1 for row in categories if not row["missing"]),
            "category_count": len(categories),
            "critical_loss_count": len(_critical_losses(losses)),
        },
    }


def _compare_values(category: str, source: set[str], target: set[str], weight: float) -> dict[str, Any]:
    if not source:
        return {
            "category": category,
            "weight": weight,
            "source_count": 0,
            "target_count": len(target),
            "score": 1.0,
            "missing": [],
            "extra": sorted(target)[:12],
        }
    missing = sorted(source - target)
    extra = sorted(target - source)
    return {
        "category": category,
        "weight": weight,
        "source_count": len(source),
        "target_count": len(target),
        "score": round((len(source) - len(missing)) / len(source), 3),
        "missing": missing[:12],
        "extra": extra[:12],
    }


def _critical_losses(losses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    critical = {"public_interfaces", "behavior_contracts"}
    return [row for row in losses if row["category"] in critical]


def _purpose_tokens(ir: dict[str, Any]) -> set[str]:
    words = {
        token
        for token in _normalize(str(ir.get("purpose") or "")).split()
        if len(token) >= 4 and token not in _PURPOSE_BOILERPLATE
    }
    return set(sorted(words)[:24])


_PURPOSE_BOILERPLATE = {
    "automation",
    "docs",
    "from",
    "inferred",
    "project",
    "python",
    "task",
    "tooling",
}


def _interface_keys(ir: dict[str, Any]) -> set[str]:
    keys = set()
    for row in list(ir.get("public_interfaces", []) or []):
        if isinstance(row, dict) and row.get("name"):
            keys.add(f"{row.get('kind') or 'interface'}:{row.get('name')}")
    return keys


def _behavior_keys(ir: dict[str, Any]) -> set[str]:
    keys = set()
    for row in list(ir.get("behavior_contracts", []) or []):
        if isinstance(row, dict) and row.get("source"):
            keys.add(str(row["source"]))
    return keys


def _slice_keys(ir: dict[str, Any]) -> set[str]:
    keys = set()
    for row in list(ir.get("architecture_slices", []) or []):
        if isinstance(row, dict) and row.get("id"):
            keys.add(str(row["id"]))
    return keys


def _acceptance_keys(ir: dict[str, Any]) -> set[str]:
    keys = set()
    for row in list(ir.get("acceptance_tests", []) or []):
        if isinstance(row, dict):
            value = row.get("id") or row.get("criterion")
        else:
            value = row
        if value:
            keys.add(str(value))
    return keys


def _data_keys(ir: dict[str, Any]) -> set[str]:
    domain = dict(ir.get("domain_model", {}))
    keys = set()
    for row in list(domain.get("data_artifacts", []) or []):
        if isinstance(row, dict):
            value = row.get("path") or row.get("name")
        else:
            value = row
        if value:
            keys.add(str(value))
    return keys


def _normalize(value: str) -> str:
    chars = [char.lower() if char.isalnum() else " " for char in value]
    return " ".join("".join(chars).split())
