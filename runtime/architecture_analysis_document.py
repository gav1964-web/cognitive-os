"""Human-readable architecture analysis document."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def write_architecture_analysis_document(
    *,
    root: Path,
    project_report: dict[str, Any],
    architecture_decision: dict[str, Any],
    technical_spec: dict[str, Any] | None = None,
    output_group: str = "foundations",
) -> Path:
    out_dir = root / "artifacts" / "roles" / output_group
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = out_dir / f"architecture_analysis_{stamp}.md"
    path.write_text(
        render_architecture_analysis_document(
            project_report=project_report,
            architecture_decision=architecture_decision,
            technical_spec=technical_spec or {},
        ),
        encoding="utf-8",
    )
    return path


def render_architecture_analysis_document(
    *,
    project_report: dict[str, Any],
    architecture_decision: dict[str, Any],
    technical_spec: dict[str, Any],
) -> str:
    content = dict(project_report.get("content", project_report))
    summary = dict(content.get("summary", {}))
    answers = dict(content.get("answers", {}))
    chosen = dict(architecture_decision.get("chosen_option", {}))
    contract = dict(technical_spec.get("extraction_contract", {}))
    lines = [
        "# Architecture Analysis",
        "",
        f"Project: {_value(project_report.get('project') or architecture_decision.get('project') or summary.get('root'))}",
        f"Goal: {_value(architecture_decision.get('goal'))}",
        "",
        "## Executive Summary",
        "",
        _value(architecture_decision.get("decision_summary")),
        "",
        f"Chosen option: {_value(chosen.get('title') or chosen.get('id'))}",
        f"Reason: {_value(chosen.get('reason'))}",
        "",
        "## Project Purpose And Boundaries",
        "",
        *_answer_lines(answers.get("1_project_purpose_and_boundaries")),
        "",
        "## Entrypoints And Execution Flow",
        "",
        *_answer_lines(answers.get("2_entrypoints_and_execution_flow")),
        "",
        "## Capability Candidates",
        "",
        *_table(
            ["Source", "Reason", "Status", "Next Step"],
            [
                [row.get("source"), row.get("reason"), row.get("status"), row.get("next_step")]
                for row in architecture_decision.get("capability_model", [])
            ],
        ),
        "",
        "## Recommended Extraction Contract",
        "",
        f"Candidate: {_value(contract.get('candidate'))}",
        f"Selection reason: {_value(contract.get('selection_reason'))}",
        "",
        "## Risks",
        "",
        *_table(
            ["Severity", "Source", "Description", "Mitigation"],
            [
                [row.get("severity"), row.get("source"), row.get("description"), row.get("mitigation")]
                for row in architecture_decision.get("risks", [])
            ],
        ),
        "",
        "## Open Questions",
        "",
        *_bullet(row.get("question") for row in architecture_decision.get("open_questions", [])),
        "",
        "## Evidence And Traceability",
        "",
        *_table(
            ["Source", "Requirement", "Target", "Acceptance"],
            [
                [row.get("source"), row.get("requirement"), row.get("target"), row.get("acceptance")]
                for row in architecture_decision.get("traceability", [])
            ],
        ),
        "",
        "## Non-Goals",
        "",
        *_bullet(architecture_decision.get("non_goals", [])),
        "",
        "## Next Step",
        "",
        _next_step(architecture_decision, technical_spec),
        "",
    ]
    return "\n".join(lines)


def _answer_lines(value: object) -> list[str]:
    if isinstance(value, dict):
        rows = []
        for key, item in value.items():
            rows.append(f"- {key}: {_value(item)}")
        return rows or ["- No structured answer available."]
    if isinstance(value, list):
        return _bullet(value)
    return [f"- {_value(value)}"]


def _table(headers: list[str], rows: list[list[object]]) -> list[str]:
    if not rows:
        return ["No evidence recorded."]
    result = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows[:12]:
        result.append("| " + " | ".join(_cell(value) for value in row) + " |")
    return result


def _bullet(values: object) -> list[str]:
    if not isinstance(values, list):
        values = list(values) if values else []
    rows = [f"- {_value(value)}" for value in values if _value(value) != "n/a"]
    return rows or ["- None recorded."]


def _next_step(architecture_decision: dict[str, Any], technical_spec: dict[str, Any]) -> str:
    if technical_spec.get("artifact_type") == "TechnicalSpec":
        contract = dict(technical_spec.get("extraction_contract", {}))
        return f"Hand off `{_value(contract.get('candidate'))}` to Implementer only after human review of this document."
    next_artifact = dict(architecture_decision.get("next_artifact", {}))
    return f"Prepare `{_value(next_artifact.get('type'))}` with {_value(next_artifact.get('recommended_role'))}."


def _cell(value: object) -> str:
    return _value(value).replace("|", "\\|").replace("\n", " ")


def _value(value: object) -> str:
    if value in (None, "", []):
        return "n/a"
    if isinstance(value, list):
        return ", ".join(_value(item) for item in value[:6])
    if isinstance(value, dict):
        return ", ".join(f"{key}={_value(item)}" for key, item in list(value.items())[:6])
    return str(value)
