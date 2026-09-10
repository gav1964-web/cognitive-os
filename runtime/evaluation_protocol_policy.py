"""Validated policy loader for three-route product evaluation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


EXPECTED_ROUTES = ["direct_agent", "short_chain", "full_chain"]
EXPECTED_RUBRIC = {
    "requirement_coverage", "correctness", "maintainability", "evidence_quality", "safety"
}


def load_evaluation_protocol_policy(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    errors = evaluation_protocol_policy_errors(payload)
    if errors:
        raise ValueError("invalid evaluation protocol policy: " + ", ".join(errors))
    return payload


def evaluation_protocol_policy_errors(payload: dict[str, Any]) -> list[str]:
    errors = []
    if payload.get("schema_version") != "evaluation_protocol.v2":
        errors.append("schema_version")
    if payload.get("routes") != EXPECTED_ROUTES:
        errors.append("routes")
    contracts = dict(payload.get("route_contracts") or {})
    if set(contracts) != set(EXPECTED_ROUTES):
        errors.append("route_contracts")
    direct = dict(contracts.get("direct_agent") or {})
    if direct.get("may_use_cognitive_os") is not False:
        errors.append("direct_agent_boundary")
    if "deterministic_direct_baseline" not in direct.get("forbidden_executors", []):
        errors.append("legacy_proxy_not_forbidden")
    rubric = dict(payload.get("rubric") or {})
    if set(rubric) != EXPECTED_RUBRIC:
        errors.append("rubric_fields")
    elif abs(sum(float(value) for value in rubric.values()) - 1.0) > 1e-9:
        errors.append("rubric_weight_sum")
    product = set(payload.get("product_task_classes") or [])
    ablation = set(payload.get("ablation_task_classes") or [])
    if not product or product & ablation:
        errors.append("task_class_tracks")
    for field in ("minimum_tasks_before_claim", "minimum_tasks_per_class_before_claim"):
        if not isinstance(payload.get(field), int) or payload[field] < 1:
            errors.append(field)
    for field in ("require_independent_judge", "require_same_model_per_task", "require_all_routes"):
        if payload.get(field) is not True:
            errors.append(field)
    if payload.get("require_judge_route_separation") is not True:
        errors.append("require_judge_route_separation")
    if payload.get("require_blind_key_withheld_until_scored") is not True:
        errors.append("require_blind_key_withheld_until_scored")
    if payload.get("legacy_metrics_are_authority") is not False:
        errors.append("legacy_metrics_authority")
    return errors
