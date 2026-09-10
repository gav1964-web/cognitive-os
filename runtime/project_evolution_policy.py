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
    for field_name in (
        "principles",
        "chosen_path",
        "development_lanes",
        "decision_rules",
        "stop_signals",
        "evidence_milestones",
        "evolution_rules",
        "evolution_change_types",
        "promotion_gates",
        "anti_patterns",
        "self_improvement",
    ):
        if not payload.get(field_name):
            raise ProjectEvolutionPolicyError(f"project evolution policy missing {field_name}")
    if not isinstance(payload.get("status_threshold"), (int, float)):
        raise ProjectEvolutionPolicyError("project evolution policy requires numeric status_threshold")
    self_improvement = dict(payload.get("self_improvement") or {})
    if not self_improvement.get("mutable_config_paths") or not self_improvement.get("promotion"):
        raise ProjectEvolutionPolicyError("self improvement requires mutable_config_paths and promotion")
    _validate_failure_class_families(self_improvement)
    return payload


def _validate_failure_class_families(self_improvement: dict[str, Any]) -> None:
    holdout = dict(self_improvement.get("hypothesis_holdout") or {})
    normalization = dict(holdout.get("signature_normalization") or {})
    families = dict(normalization.get("failure_class_families") or {})
    owners: dict[str, str] = {}
    for family, members in families.items():
        canonical = str(family).strip()
        aliases = [str(value).strip() for value in members or []]
        if not canonical or not aliases or any(not value for value in aliases):
            raise ProjectEvolutionPolicyError("failure class families require named families and aliases")
        for value in [canonical, *aliases]:
            if value in owners and owners[value] != canonical:
                raise ProjectEvolutionPolicyError(f"failure class alias {value} belongs to multiple families")
            owners[value] = canonical


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
    blockers = sorted(set(_anti_pattern_blockers(change, policy)) | set(_rule_blockers(change, evidence, policy)))
    gate_reports = {
        name: _gate_status(score, evidence, change, dict(gate))
        for name, gate in dict(policy.get("promotion_gates") or {}).items()
    }
    readiness = _readiness(score, missing, blockers, policy)
    gate_ok = any(dict(row).get("passed") for row in gate_reports.values())
    status_ok = not blockers and (gate_ok or readiness >= float(policy.get("status_threshold") or 0.8))
    return {
        "artifact_type": "ProjectEvolutionReport",
        "status": "ok" if status_ok else "needs_work",
        "evolution_score": score,
        "readiness": readiness,
        "missing_evidence": missing,
        "blockers": blockers,
        "rules": sorted(dict(policy.get("evolution_rules") or {})),
        "promotion_gates": gate_reports,
    }


def _anti_pattern_blockers(change: dict[str, Any], policy: dict[str, Any]) -> list[str]:
    declared = {str(item) for item in list(change.get("anti_patterns") or []) if item}
    known = {str(item) for item in list(policy.get("anti_patterns") or [])}
    return sorted(declared & known)


def _rule_blockers(change: dict[str, Any], evidence: set[str], policy: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    target_gates = {str(item) for item in list(change.get("target_gates") or []) if item}
    for rule in dict(policy.get("evolution_rules") or {}).values():
        row = dict(rule or {})
        blocker = str(row.get("blocker") or "")
        if not blocker:
            continue
        if _blocked_gate_applies(row, target_gates) and str(row.get("required_evidence") or "") not in evidence:
            blockers.append(blocker)
        if row.get("metric") and int(change.get(str(row["metric"])) or 0) > 0:
            blockers.append(blocker)
        if row.get("boundary_track") and change.get("boundary_track") == row["boundary_track"]:
            required = str(row.get("required_evidence") or "")
            if required and required not in evidence:
                blockers.append(blocker)
        if row.get("blocker") == "line_limit_check_missing" and "line_limit_check" not in evidence:
            blockers.append(blocker)
    return sorted(set(blockers))


def _blocked_gate_applies(rule: dict[str, Any], target_gates: set[str]) -> bool:
    blocked_gate = str(rule.get("blocked_gate") or "")
    return bool(blocked_gate and blocked_gate in target_gates)


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
