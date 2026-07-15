"""Analytics and policy-gap reports for L4.5 semantic benchmarks."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RISK_BOUNDARIES = {"bounded_with_risks", "unsupported_product_surface"}
SAFE_RISK_ACTIONS = {
    "ask_clarification",
    "stop_unsupported",
    "record_template_backlog_requires_human_review",
    "blocked",
}


def analyze_l45_semantic_benchmark(
    report: dict[str, Any],
    *,
    write_path: Path | None = None,
) -> dict[str, Any]:
    """Build aggregate route and corpus stats from a semantic benchmark report."""

    rows = list(report.get("cases", [])) if isinstance(report.get("cases"), list) else []
    boundary_counts = Counter(_actual(row).get("prompt_boundary") or "unknown" for row in rows)
    action_counts = Counter(_actual(row).get("l4_action") or "unknown" for row in rows)
    category_counts = Counter(_case_category(row) for row in rows)
    summary = dict(report.get("summary", {})) if isinstance(report.get("summary"), dict) else {}
    analytics = {
        "artifact_type": "L45SemanticCorpusAnalyticsReport",
        "status": "ok",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_report": {
            "artifact_type": report.get("artifact_type"),
            "status": report.get("status"),
            "model_quality_mode": report.get("model_quality_mode"),
            "corpus": dict(report.get("corpus", {})) if isinstance(report.get("corpus"), dict) else {},
        },
        "summary": {
            "case_count": len(rows),
            "passed": int(summary.get("passed") or 0),
            "failed": int(summary.get("failed") or 0),
            "escalated": int(summary.get("escalated") or 0),
            "validated": int(summary.get("validated") or 0),
            "backlog_created": sum(1 for row in rows if _actual(row).get("backlog_created") is True),
            "risk_or_unsupported_cases": sum(
                1 for row in rows if (_actual(row).get("prompt_boundary") or "") in RISK_BOUNDARIES
            ),
            "model_used": int(summary.get("model_used") or 0),
            "model_fallbacks": int(summary.get("model_fallbacks") or 0),
        },
        "boundary_counts": dict(sorted(boundary_counts.items())),
        "action_counts": dict(sorted(action_counts.items())),
        "category_counts": dict(sorted(category_counts.items())),
        "policy_signals": _policy_signals(rows),
    }
    if write_path is not None:
        write_path.parent.mkdir(parents=True, exist_ok=True)
        write_path.write_text(json.dumps(analytics, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        analytics["report_path"] = write_path.as_posix()
    return analytics


def build_l45_risk_policy_gap_report(
    report: dict[str, Any],
    *,
    write_path: Path | None = None,
) -> dict[str, Any]:
    """Find benchmark cases where L4 policy still treats risky prompts too permissively."""

    rows = list(report.get("cases", [])) if isinstance(report.get("cases"), list) else []
    gaps = [_gap(row) for row in rows]
    gaps = [item for item in gaps if item is not None]
    severities = Counter(str(item["severity"]) for item in gaps)
    result = {
        "artifact_type": "L45RiskPolicyGapReport",
        "status": "gaps_found" if gaps else "ok",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_report": {
            "artifact_type": report.get("artifact_type"),
            "status": report.get("status"),
            "model_quality_mode": report.get("model_quality_mode"),
            "corpus": dict(report.get("corpus", {})) if isinstance(report.get("corpus"), dict) else {},
        },
        "summary": {
            "case_count": len(rows),
            "gap_count": len(gaps),
            "high": int(severities.get("high") or 0),
            "medium": int(severities.get("medium") or 0),
        },
        "gaps": gaps,
        "policy_recommendations": _recommendations(gaps),
    }
    if write_path is not None:
        write_path.parent.mkdir(parents=True, exist_ok=True)
        write_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        result["report_path"] = write_path.as_posix()
    return result


def _actual(row: dict[str, Any]) -> dict[str, Any]:
    actual = row.get("actual", {})
    return dict(actual) if isinstance(actual, dict) else {}


def _case_category(row: dict[str, Any]) -> str:
    case_id = str(row.get("case_id") or "")
    expected = row.get("expected", {})
    expected_action = str(dict(expected).get("l4_action") if isinstance(expected, dict) else "")
    if case_id.startswith("generated_"):
        case_id = "_".join(case_id.split("_")[2:])
    if case_id.startswith("known_") or expected_action == "build_verified_system_package":
        return "known_template"
    if expected_action in {"ask_clarification", "stop_unsupported"}:
        return "clarification_or_unsupported"
    if expected_action == "record_template_backlog_requires_human_review":
        return "risk_boundary"
    return "unknown_template"


def _policy_signals(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "normal_backlog": sum(1 for row in rows if _actual(row).get("l4_action") == "record_template_backlog"),
        "risk_backlog_human_review": sum(
            1 for row in rows if _actual(row).get("l4_action") == "record_template_backlog_requires_human_review"
        ),
        "risk_boundary_to_normal_backlog": sum(
            1
            for row in rows
            if (_actual(row).get("prompt_boundary") or "") in RISK_BOUNDARIES
            and _actual(row).get("l4_action") == "record_template_backlog"
        ),
    }


def _gap(row: dict[str, Any]) -> dict[str, Any] | None:
    actual = _actual(row)
    boundary = str(actual.get("prompt_boundary") or "unknown")
    action = str(actual.get("l4_action") or "unknown")
    if boundary not in RISK_BOUNDARIES or action in SAFE_RISK_ACTIONS:
        return None
    severity = "high" if boundary == "unsupported_product_surface" else "medium"
    return {
        "case_id": row.get("case_id"),
        "severity": severity,
        "prompt_boundary": boundary,
        "l4_action": action,
        "policy_gap": "risk_or_unsupported_prompt_routed_without_extra_gate",
        "recommendation": "route to clarification, stop_unsupported, or risk backlog requiring human review",
    }


def _recommendations(gaps: list[dict[str, Any]]) -> list[str]:
    if not gaps:
        return ["No risky or unsupported benchmark case reached normal template backlog."]
    recommendations = []
    if any(item["prompt_boundary"] == "unsupported_product_surface" for item in gaps):
        recommendations.append("Unsupported product surfaces must be clarified or stopped before template backlog.")
    if any(item["prompt_boundary"] == "bounded_with_risks" for item in gaps):
        recommendations.append("Risk-marked prompts must require explicit human review before template admission.")
    return recommendations
