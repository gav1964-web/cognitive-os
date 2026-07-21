"""Failure analysis for model-backed L4.5 semantic evaluations."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def analyze_l45_model_failures(
    *,
    suite_report: dict[str, Any] | None = None,
    comparison_reports: list[dict[str, Any]] | None = None,
    write_path: Path | None = None,
) -> dict[str, Any]:
    comparisons = list(comparison_reports or [])
    if suite_report:
        comparisons.extend(_comparisons_from_suite(suite_report))
    cases = [case for report in comparisons for case in report.get("cases", [])]
    failed = [_failure_case(case) for case in cases if _is_model_failure(case)]
    failed_codes = Counter(code for case in failed for code in case["validation_failed_codes"])
    actions = Counter(str(case["model_action"]) for case in failed)
    report = {
        "artifact_type": "L45ModelFailureAnalysisReport",
        "status": "ok",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "comparison_count": len(comparisons),
            "case_count": len(cases),
            "model_failure_count": len(failed),
            "failed_code_counts": dict(sorted(failed_codes.items())),
            "model_action_counts": dict(sorted(actions.items())),
        },
        "failures": failed,
        "recommendations": _recommendations(failed_codes),
    }
    if write_path is not None:
        write_path.parent.mkdir(parents=True, exist_ok=True)
        write_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = write_path.as_posix()
    return report


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _comparisons_from_suite(suite_report: dict[str, Any]) -> list[dict[str, Any]]:
    reports = []
    for profile in suite_report.get("profiles", []):
        comparison_path = dict(profile.get("comparison", {})).get("report_path") if isinstance(profile, dict) else None
        if comparison_path and Path(comparison_path).is_file():
            reports.append(load_json(Path(comparison_path)))
    return reports


def _is_model_failure(case: dict[str, Any]) -> bool:
    model = dict(case.get("model", {}))
    deterministic = dict(case.get("deterministic", {}))
    return model.get("status") != "ok" and deterministic.get("status") == "ok"


def _failure_case(case: dict[str, Any]) -> dict[str, Any]:
    model = dict(case.get("model", {}))
    deterministic = dict(case.get("deterministic", {}))
    failed_codes = model.get("validation_failed_codes") or []
    return {
        "case_id": case.get("case_id"),
        "verdict": case.get("verdict"),
        "deterministic_action": deterministic.get("l4_action"),
        "model_action": model.get("l4_action"),
        "model_error": model.get("model_error"),
        "validation_failed_codes": [str(code) for code in failed_codes],
        "raw_model_output_used": model.get("raw_model_output_used"),
    }


def _recommendations(failed_codes: Counter[str]) -> list[str]:
    recommendations = []
    if failed_codes.get("risks_present"):
        recommendations.append("Keep synthesizing explicit default risks for otherwise valid model proposals.")
    if failed_codes.get("proposal_payload_present"):
        recommendations.append("Improve proposal payload hardening for empty model proposal bodies.")
    if failed_codes.get("evidence_present"):
        recommendations.append("Require model prompt to cite concrete evidence refs from SemanticEvidencePack.")
    if not recommendations:
        recommendations.append("No repeated model failure class detected in comparison reports.")
    return recommendations
