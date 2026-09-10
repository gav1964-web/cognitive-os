"""Independent blind scoring for the three-route evaluation protocol."""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from typing import Any


def score_blind_evaluation(
    *,
    bundle: dict[str, Any],
    blind_key: dict[str, Any],
    scorecard: dict[str, Any],
    receipts: list[dict[str, Any]],
    policy: dict[str, Any],
) -> dict[str, Any]:
    errors = _validate_inputs(bundle, blind_key, scorecard, policy)
    mapping = {str(row["candidate_id"]): str(row["route"]) for row in blind_key.get("mapping", [])}
    candidates = {str(row["candidate_id"]): row for row in bundle.get("candidates", [])}
    receipt_index = {(str(row["task_id"]), str(row["route"])): row for row in receipts}
    weights = dict(policy["rubric"])
    scored: list[dict[str, Any]] = []
    seen_scores: set[tuple[str, str]] = set()
    for row in scorecard.get("scores", []):
        candidate_id = str(row.get("candidate_id") or "")
        route = mapping.get(candidate_id)
        if route is None:
            errors.append(f"unknown_candidate:{candidate_id}")
            continue
        score_key = (str(row.get("task_id") or ""), candidate_id)
        if score_key in seen_scores:
            errors.append(f"duplicate_score:{score_key[0]}:{candidate_id}")
            continue
        seen_scores.add(score_key)
        if score_key[0] != str(candidates.get(candidate_id, {}).get("task_id") or ""):
            errors.append(f"candidate_task_mismatch:{candidate_id}")
            continue
        rubric = dict(row.get("rubric") or {})
        missing = sorted(set(weights) - set(rubric))
        if missing:
            errors.append(f"missing_rubric:{candidate_id}:{','.join(missing)}")
            continue
        if any(not isinstance(rubric[name], (int, float)) or not 0 <= rubric[name] <= 10 for name in weights):
            errors.append(f"invalid_rubric_score:{candidate_id}")
            continue
        weighted = round(sum(float(rubric[name]) * float(weight) for name, weight in weights.items()), 3)
        scored.append({
            "task_id": str(row["task_id"]), "task_class": str(candidates[candidate_id]["task_class"]),
            "candidate_id": candidate_id, "route": route, "weighted_score": weighted,
            "rubric": rubric, "blocking_findings": list(row.get("blocking_findings") or []),
        })
    expected = {(str(row["task_id"]), str(row["candidate_id"])) for row in bundle.get("candidates", [])}
    observed = {(row["task_id"], row["candidate_id"]) for row in scored}
    if expected != observed:
        errors.append("scorecard_candidate_coverage_incomplete")
    if errors:
        raise ValueError("blind score rejected: " + "; ".join(sorted(set(errors))))
    tasks = _task_results(scored, float(policy.get("winner_margin", 0.25)))
    by_class = _aggregate(scored, "task_class")
    by_route = _aggregate(scored, "route")
    operations = _operational_metrics(receipt_index)
    minimum = int(policy.get("minimum_tasks_before_claim", 20))
    product_classes = set(policy.get("product_task_classes") or [])
    product_tasks = [row for row in tasks if row["task_class"] in product_classes]
    complete = sum(1 for row in product_tasks if row["winner"] != "incomplete")
    class_counts = {
        task_class: sum(
            row["task_class"] == task_class and row["winner"] != "incomplete"
            for row in product_tasks
        )
        for task_class in sorted(product_classes)
    }
    class_minimum = int(policy.get("minimum_tasks_per_class_before_claim", 2))
    class_coverage_ok = bool(class_counts) and all(value >= class_minimum for value in class_counts.values())
    all_tasks_complete = len(tasks) == len(bundle.get("tasks", [])) and all(
        row["winner"] != "incomplete" for row in tasks
    )
    return {
        "artifact_type": "ThreeRouteEvaluationReport",
        "schema_version": "three_route_evaluation_report.v2",
        "status": "evaluated" if all_tasks_complete else "incomplete",
        "bundle_digest": bundle["bundle_digest"],
        "judge": scorecard["judge"],
        "task_results": tasks,
        "quality_by_task_class": by_class,
        "quality_by_route": by_route,
        "operations_by_route": operations,
        "product_task_count": len(product_tasks),
        "ablation_task_count": len(tasks) - len(product_tasks),
        "product_class_counts": class_counts,
        "claim_eligible": complete >= minimum and class_coverage_ok,
        "limitations": _limitations(complete, minimum, class_coverage_ok, class_minimum),
    }


def _validate_inputs(
    bundle: dict[str, Any], key: dict[str, Any], scorecard: dict[str, Any], policy: dict[str, Any]
) -> list[str]:
    errors = []
    if bundle.get("bundle_digest") != _unsigned_digest(bundle, "bundle_digest"):
        errors.append("bundle_digest_mismatch")
    if key.get("key_digest") != _unsigned_digest(key, "key_digest"):
        errors.append("blind_key_digest_mismatch")
    if key.get("bundle_digest") != bundle.get("bundle_digest"):
        errors.append("blind_key_bundle_mismatch")
    candidate_ids = [str(row.get("candidate_id") or "") for row in bundle.get("candidates", [])]
    key_ids = [str(row.get("candidate_id") or "") for row in key.get("mapping", [])]
    if len(candidate_ids) != len(set(candidate_ids)) or len(key_ids) != len(set(key_ids)):
        errors.append("candidate_mapping_not_unique")
    if set(candidate_ids) != set(key_ids):
        errors.append("candidate_mapping_incomplete")
    judge = scorecard.get("judge")
    if not isinstance(judge, dict) or not judge.get("id"):
        errors.append("judge_identity_missing")
    elif policy.get("require_independent_judge") and judge.get("independent") is not True:
        errors.append("independent_judge_required")
    elif policy.get("require_independent_judge") and (
        judge.get("produced_route_output") is not False
        or judge.get("saw_blind_key_before_scoring") is not False
    ):
        errors.append("judge_independence_boundary_incomplete")
    if scorecard.get("bundle_digest") != bundle.get("bundle_digest"):
        errors.append("scorecard_bundle_mismatch")
    return errors


def _task_results(rows: list[dict[str, Any]], margin: float) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["task_id"]].append(row)
    results = []
    for task_id, candidates in sorted(grouped.items()):
        ordered = sorted(candidates, key=lambda row: row["weighted_score"], reverse=True)
        complete = {row["route"] for row in ordered} == {"direct_agent", "short_chain", "full_chain"}
        winner = "incomplete"
        if complete:
            acceptable = [row for row in ordered if not row["blocking_findings"]]
            if not acceptable:
                winner = "no_acceptable_route"
            elif len(acceptable) == 1:
                winner = acceptable[0]["route"]
            else:
                winner = "tie" if acceptable[0]["weighted_score"] - acceptable[1]["weighted_score"] < margin else acceptable[0]["route"]
        results.append({
            "task_id": task_id, "task_class": ordered[0]["task_class"], "winner": winner,
            "scores": {row["route"]: row["weighted_score"] for row in ordered},
        })
    return results


def _aggregate(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        grouped[str(row[field])].append(float(row["weighted_score"]))
    return {
        key: {"count": len(values), "mean": round(sum(values) / len(values), 3)}
        for key, values in sorted(grouped.items())
    }


def _operational_metrics(receipts: dict[tuple[str, str], dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for (_, route), receipt in receipts.items():
        grouped[route].append(receipt)
    result = {}
    for route, rows in sorted(grouped.items()):
        result[route] = {
            "runs": len(rows),
            "runtime_seconds": round(sum(float(row["runtime_seconds"]) for row in rows), 3),
            "estimated_cost": round(sum(float(row["estimated_cost"]) for row in rows), 6),
            "manual_corrections": sum(len(row.get("manual_corrections") or []) for row in rows),
            "human_correction_minutes": round(sum(
                float(item.get("minutes") or 0)
                for row in rows for item in row.get("manual_corrections") or []
            ), 3),
            "input_tokens": sum(int(dict(row["token_usage"]).get("input") or 0) for row in rows),
            "output_tokens": sum(int(dict(row["token_usage"]).get("output") or 0) for row in rows),
        }
    return result


def _unsigned_digest(payload: dict[str, Any], digest_field: str) -> str:
    unsigned = {key: value for key, value in payload.items() if key != digest_field}
    encoded = json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _limitations(complete: int, minimum: int, class_ok: bool, class_minimum: int) -> list[str]:
    values = []
    if complete < minimum:
        values.append(f"requires at least {minimum} complete product tasks")
    if not class_ok:
        values.append(f"requires at least {class_minimum} tasks in every claimed product class")
    return values
