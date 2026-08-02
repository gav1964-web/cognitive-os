"""Policy-backed project evolution gates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "config" / "project_evolution_policy.json"


class ProjectEvolutionPolicyError(RuntimeError):
    """Raised when project evolution policy is invalid."""


def load_project_evolution_policy(path: str | None = None) -> dict[str, Any]:
    payload = json.loads(Path(path or DEFAULT_PATH).read_text(encoding="utf-8"))
    if payload.get("schema_version") != "project_evolution_policy.v1":
        raise ProjectEvolutionPolicyError("project evolution policy must use schema_version project_evolution_policy.v1")
    for field_name in ("principles", "evolution_change_types", "promotion_gates", "anti_patterns"):
        if not payload.get(field_name):
            raise ProjectEvolutionPolicyError(f"project evolution policy missing {field_name}")
    if not isinstance(payload.get("status_threshold"), (int, float)):
        raise ProjectEvolutionPolicyError("project evolution policy requires numeric status_threshold")
    return payload


def evaluate_project_evolution(change: dict[str, Any], *, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or load_project_evolution_policy()
    evidence = {str(item) for item in list(change.get("evidence") or []) if item}
    change_types = [str(item) for item in list(change.get("change_types") or []) if item]
    score = 0
    missing: list[str] = []
    for change_type in change_types:
        row = dict(dict(policy.get("evolution_change_types") or {}).get(change_type) or {})
        if not row:
            missing.append(f"unknown_change_type:{change_type}")
            continue
        required = {str(item) for item in list(row.get("required_evidence") or [])}
        missing.extend(f"{change_type}:{item}" for item in sorted(required - evidence))
        if required.issubset(evidence):
            score += int(row.get("score") or 0)
    blockers = _anti_pattern_blockers(change, policy)
    gate_reports = {
        name: _gate_status(score, evidence, change, dict(gate))
        for name, gate in dict(policy.get("promotion_gates") or {}).items()
    }
    readiness = _readiness(score, missing, blockers, policy)
    gate_ok = any(dict(row).get("passed") for row in gate_reports.values())
    return {
        "artifact_type": "ProjectEvolutionReport",
        "status": "ok" if gate_ok or readiness >= float(policy.get("status_threshold") or 0.8) else "needs_work",
        "evolution_score": score,
        "readiness": readiness,
        "missing_evidence": missing,
        "blockers": blockers,
        "promotion_gates": gate_reports,
    }


def _anti_pattern_blockers(change: dict[str, Any], policy: dict[str, Any]) -> list[str]:
    declared = {str(item) for item in list(change.get("anti_patterns") or []) if item}
    known = {str(item) for item in list(policy.get("anti_patterns") or [])}
    return sorted(declared & known)


def _gate_status(score: int, evidence: set[str], change: dict[str, Any], gate: dict[str, Any]) -> dict[str, Any]:
    required = {str(item) for item in list(gate.get("required_evidence") or [])}
    delta = int(change.get("field_callable_delta") or 0)
    missing = sorted(required - evidence)
    score_ok = score >= int(gate.get("minimum_recent_evolution_score") or 0)
    delta_ok = delta >= int(gate.get("minimum_field_callable_delta") or 0)
    passed = not missing and score_ok and delta_ok
    return {"passed": passed, "missing_evidence": missing, "score_ok": score_ok, "field_delta_ok": delta_ok}


def _readiness(score: int, missing: list[str], blockers: list[str], policy: dict[str, Any]) -> float:
    gate_scores = [int(row.get("score") or 0) for row in dict(policy.get("evolution_change_types") or {}).values()]
    denominator = max(1, sum(gate_scores))
    base = min(1.0, score / denominator)
    penalty = min(0.8, 0.1 * len(missing) + 0.25 * len(blockers))
    return round(max(0.0, base - penalty), 3)
