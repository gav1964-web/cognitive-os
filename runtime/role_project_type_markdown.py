"""Markdown rendering for role/project-type evaluation reports."""

from __future__ import annotations

from typing import Any


def render_role_project_type_markdown(report: dict[str, Any]) -> str:
    roles = list(dict(report.get("roles") or {}))
    lines = ["# Role maturity by project type", "", "| Project stratum | " + " | ".join(roles) + " |"]
    lines.append("| --- | " + " | ".join("---:" for _ in roles) + " |")
    for row in report.get("heatmap", []):
        values = []
        cells = dict(row.get("roles") or {})
        for role in roles:
            cell = dict(cells.get(role) or {})
            score = cell.get("score")
            values.append("-" if score is None else f"{score:.2f} ({cell.get('maturity')})")
        lines.append(f"| {row.get('label')} | " + " | ".join(values) + " |")
    lines.extend(["", "## Priority queue", ""])
    for index, row in enumerate(report.get("priority_queue", [])[:10], start=1):
        score = "unmeasured" if row["score"] is None else f"{row['score']:.2f}"
        lines.append(
            f"{index}. `{row['role_id']} x {row['project_stratum']}`: "
            f"{score}, priority {row['priority_score']:.2f}; "
            f"{', '.join(row['evidence_gaps']) or 'score gap'}"
        )
    debt = dict(report.get("classification_debt") or {})
    lines.extend(["", "## Classification debt", ""])
    if not debt.get("items"):
        lines.append("No unclassified project archetypes.")
    for row in debt.get("items", []):
        signals = sorted(set(row.get("project_archetypes", []) + row.get("contract_families", [])))
        lines.append(
            f"- `{row['project']}`: {', '.join(signals) or 'no authoritative archetype signals'}; "
            f"{row['next_action']}"
        )
    lifecycle = dict(report.get("unknown_project_lifecycle") or {})
    lines.extend(["", "## Unknown project lifecycle", ""])
    lines.append(
        f"Status: `{lifecycle.get('status', 'clear')}`; "
        f"intakes: {lifecycle.get('intake_count', 0)}; "
        f"provisional candidates: {lifecycle.get('provisional_candidate_count', 0)}."
    )
    return "\n".join(lines) + "\n"
