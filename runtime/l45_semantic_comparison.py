"""Compare deterministic and model-backed L4.5 semantic benchmark reports."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def compare_l45_semantic_reports(
    *,
    deterministic_report: dict[str, Any],
    model_report: dict[str, Any],
    write_path: Path | None = None,
) -> dict[str, Any]:
    det_cases = {str(row.get("case_id")): row for row in deterministic_report.get("cases", [])}
    model_cases = {str(row.get("case_id")): row for row in model_report.get("cases", [])}
    case_ids = sorted(set(det_cases) | set(model_cases))
    rows = [_compare_case(case_id, det_cases.get(case_id), model_cases.get(case_id)) for case_id in case_ids]
    report = {
        "artifact_type": "L45SemanticComparisonReport",
        "status": "ok",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "case_count": len(rows),
            "same_action": sum(1 for row in rows if row["same_action"]),
            "model_better": sum(1 for row in rows if row["verdict"] == "model_better"),
            "deterministic_better": sum(1 for row in rows if row["verdict"] == "deterministic_better"),
            "no_clear_difference": sum(1 for row in rows if row["verdict"] == "no_clear_difference"),
            "model_contract_pass_rate": _rate(model_cases.values(), "validation_status", "accepted"),
            "deterministic_contract_pass_rate": _rate(det_cases.values(), "validation_status", "accepted"),
            "model_fallback_count": sum(1 for row in model_cases.values() if row.get("actual", {}).get("model_error")),
            "model_used_count": sum(1 for row in model_cases.values() if row.get("actual", {}).get("raw_model_output_used")),
            "forbidden_action_strip_count": sum(1 for row in model_cases.values() if row.get("actual", {}).get("forbidden_actions_stripped")),
        },
        "cases": rows,
        "interpretation": _interpretation(rows, model_cases.values()),
    }
    if write_path is not None:
        write_path.parent.mkdir(parents=True, exist_ok=True)
        write_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = write_path.as_posix()
    return report


def load_report(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _compare_case(case_id: str, det: dict[str, Any] | None, model: dict[str, Any] | None) -> dict[str, Any]:
    det_actual = dict((det or {}).get("actual", {}))
    model_actual = dict((model or {}).get("actual", {}))
    det_ok = (det or {}).get("status") == "ok"
    model_ok = (model or {}).get("status") == "ok"
    same_action = det_actual.get("l4_action") == model_actual.get("l4_action")
    if model_ok and not det_ok:
        verdict = "model_better"
    elif det_ok and not model_ok:
        verdict = "deterministic_better"
    else:
        verdict = "no_clear_difference"
    return {
        "case_id": case_id,
        "verdict": verdict,
        "same_action": same_action,
        "deterministic": {
            "status": (det or {}).get("status"),
            "l4_action": det_actual.get("l4_action"),
            "hypothesis_type": det_actual.get("hypothesis_type"),
            "validation_status": det_actual.get("validation_status"),
        },
        "model": {
            "status": (model or {}).get("status"),
            "l4_action": model_actual.get("l4_action"),
            "hypothesis_type": model_actual.get("hypothesis_type"),
            "validation_status": model_actual.get("validation_status"),
            "raw_model_output_used": model_actual.get("raw_model_output_used"),
            "model_error": model_actual.get("model_error"),
        },
    }


def _rate(rows: Any, field: str, expected: str) -> float:
    relevant = [row for row in rows if row.get("actual", {}).get(field) is not None]
    if not relevant:
        return 0.0
    hits = sum(1 for row in relevant if row.get("actual", {}).get(field) == expected)
    return round(hits / len(relevant), 3)


def _interpretation(rows: list[dict[str, Any]], model_rows: Any) -> dict[str, Any]:
    model_errors = [row.get("actual", {}).get("model_error") for row in model_rows if row.get("actual", {}).get("model_error")]
    if model_errors:
        return {
            "verdict": "model_path_degraded",
            "reason": "model-backed run fell back on at least one case",
            "recommendation": "keep model use in propose-only or human-review mode until provider reliability is proven",
        }
    if any(row["verdict"] == "model_better" for row in rows):
        return {
            "verdict": "model_adds_signal",
            "reason": "model-backed run improved at least one benchmark case",
            "recommendation": "inspect replay records before crystallizing any pattern",
        }
    return {
        "verdict": "no_measured_model_advantage",
        "reason": "model run did not beat deterministic route on benchmark status",
        "recommendation": "prefer deterministic L4.0 route unless semantic corpus shows stronger model value",
    }
