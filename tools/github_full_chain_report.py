"""Render compact full-chain field-trial reports."""

from __future__ import annotations

from typing import Any


def markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        f"# {report['milestone']}",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Projects: `{report['project_count']}`",
        f"Worst case: `{summary['worst_case_score']}`",
        f"Ready by worst case: `{summary['ready_by_worst_case']}`",
        f"Needs review: `{summary['needs_review']}`",
        "",
        "## Cases",
    ]
    for case in report["cases"]:
        failed = ", ".join(item["code"] for item in case.get("failed_checks", [])) or "none"
        lines.extend([
            f"### {case['project']}",
            f"- status: `{case['status']}`",
            f"- quality: `{case['quality_score']}`",
            f"- targets: `{case.get('target_chain', {})}`",
            f"- executor: `{case.get('executor', {})}`",
            f"- failed checks: `{failed}`",
            "",
        ])
    return "\n".join(lines)
