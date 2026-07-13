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
        *_answer_lines(_first_answer(answers, "1_project_purpose_and_boundaries", "1_scope")),
        "",
        "## Entrypoints And Execution Flow",
        "",
        *_answer_lines(_first_answer(answers, "2_entrypoints_and_execution_flow", "2_execution")),
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
        "## Improvement Recommendations",
        "",
        *_improvement_recommendations(answers),
        "",
        "## Target Architecture Sketch",
        "",
        *_target_architecture_sketch(answers),
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


def _first_answer(answers: dict[str, Any], *keys: str) -> object:
    for key in keys:
        value = answers.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def _answer_lines(value: object) -> list[str]:
    if isinstance(value, dict):
        rows = []
        for key, item in value.items():
            rows.append(f"- {key}: {_value(item)}")
        return rows or ["- No structured answer available."]
    if isinstance(value, list):
        return _bullet(value)
    return [f"- {_value(value)}"]


def _improvement_recommendations(answers: dict[str, Any]) -> list[str]:
    readiness = dict(answers.get("6_runtime_extraction_readiness", {}))
    recommendations: list[str] = []

    hidden = _target_refs(readiness.get("hidden_orchestrators", []))
    if hidden:
        recommendations.append(
            "Split hidden orchestrators or large control surfaces: " + ", ".join(hidden[:4]) + "."
        )

    process_boundaries = _target_refs(readiness.get("process_boundary_candidates", []))
    if process_boundaries:
        recommendations.append(
            "Isolate process/network/filesystem-heavy boundaries before retry or replay: "
            + ", ".join(process_boundaries[:4])
            + "."
        )

    idempotency = _target_refs(readiness.get("idempotency_risks", []), key="target")
    if idempotency:
        recommendations.append(
            "Define idempotency and resume policy for side-effecting operations: "
            + ", ".join(idempotency[:4])
            + "."
        )

    quarantine = _target_refs(readiness.get("quarantine_candidates", []), key="target")
    if quarantine:
        recommendations.append(
            "Add quarantine policy for unstable dependencies or external boundaries: "
            + ", ".join(quarantine[:4])
            + "."
        )

    strategy = readiness.get("contract_test_strategy")
    if isinstance(strategy, list) and strategy:
        recommendations.append("Add contract tests around: " + ", ".join(_value(item) for item in strategy[:4]) + ".")

    extraction_plan = dict(readiness.get("minimal_extraction_plan", {}))
    capabilities = _target_refs(extraction_plan.get("capabilities_to_extract", []), key="capability")
    if capabilities:
        recommendations.append("Start with bounded extraction candidates: " + ", ".join(capabilities[:4]) + ".")

    return [f"- {item}" for item in recommendations] or ["- No structured recommendations available."]


def _target_architecture_sketch(answers: dict[str, Any]) -> list[str]:
    scope = dict(answers.get("1_scope", {}))
    execution = dict(answers.get("2_execution", {}))
    readiness = dict(answers.get("6_runtime_extraction_readiness", {}))
    rows: list[str] = []

    entrypoints = _strings(execution.get("entrypoints"))
    if entrypoints:
        rows.append("Keep entrypoints thin: " + ", ".join(entrypoints[:4]) + ".")

    scenarios = " ".join(_strings(scope.get("supported_scenarios"))).lower()
    if "http" in scenarios or execution.get("primary_execution_path"):
        rows.append("Move route handlers into an API/web boundary layer that validates requests and delegates work.")

    hidden = _target_refs(readiness.get("hidden_orchestrators", []))
    if hidden:
        rows.append("Move orchestration out of large handlers into application services: " + ", ".join(hidden[:4]) + ".")

    lifecycle = readiness.get("data_lifecycle", [])
    if isinstance(lifecycle, list) and lifecycle:
        stages = [str(row.get("stage")) for row in lifecycle if isinstance(row, dict) and row.get("stage")]
        if stages:
            rows.append("Make the data lifecycle explicit as separate stages: " + " -> ".join(stages[:5]) + ".")

    process_boundaries = _target_refs(readiness.get("process_boundary_candidates", []))
    if process_boundaries:
        rows.append("Wrap subprocess/network/filesystem boundaries behind adapters with timeouts and failure packets.")

    state = readiness.get("long_lived_state", [])
    if isinstance(state, list) and state:
        kinds = [str(row.get("kind")) for row in state if isinstance(row, dict) and row.get("kind")]
        if kinds:
            rows.append("Define state ownership and checkpoints for: " + ", ".join(dict.fromkeys(kinds[:5])) + ".")

    capabilities = _target_refs(
        dict(readiness.get("minimal_extraction_plan", {})).get("capabilities_to_extract", []),
        key="capability",
    )
    if capabilities:
        rows.append("Extract reusable pure/core capabilities first: " + ", ".join(capabilities[:4]) + ".")

    return [f"- {row}" for row in rows] or ["- No target architecture sketch available."]


def _target_refs(rows: object, *, key: str | None = None) -> list[str]:
    if not isinstance(rows, list):
        return []
    refs: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if key and row.get(key):
            refs.append(str(row.get(key)))
            continue
        path = row.get("path")
        name = row.get("name")
        target = row.get("target")
        if path and name:
            refs.append(f"{path}:{name}")
        elif target:
            refs.append(str(target))
    return refs


def _strings(value: object) -> list[str]:
    if isinstance(value, list):
        return [_value(item) for item in value if _value(item) != "n/a"]
    if value in (None, "", []):
        return []
    return [_value(value)]


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
