"""Role-scoped question answers over Project Analyzer evidence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .role_definitions import role_question_count
from .role_questionnaire_sections import build_questionnaire_sections


QUESTION_COUNT_PER_ROLE = role_question_count()


def build_role_questionnaire_report(
    *,
    project: str,
    goal_report: dict[str, Any],
    interpretation: dict[str, Any],
) -> dict[str, Any]:
    """Build a deterministic role Q/A report from bounded project evidence."""

    context = _Context(goal_report=goal_report, interpretation=interpretation)
    sections = build_questionnaire_sections(context)
    total = sum(len(section["answers"]) for section in sections)
    return {
        "artifact_type": "RoleQuestionnaireReport",
        "status": "ok",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project": project,
        "policy": {
            "answers_are_evidence_bound": True,
            "role_answers_are_not_ground_truth": True,
            "llm_invoked": False,
            "source_project_modified": False,
        },
        "question_count": total,
        "roles": sections,
        "summary": {
            "role_count": len(sections),
            "question_count_per_role": {section["role"]: len(section["answers"]) for section in sections},
            "roles_without_full_question_set": [
                section["role"]
                for section in sections
                if QUESTION_COUNT_PER_ROLE and len(section["answers"]) < QUESTION_COUNT_PER_ROLE
            ],
            "high_confidence_answers": sum(
                1
                for section in sections
                for answer in section["answers"]
                if answer.get("confidence") == "high"
            ),
            "gap_count": sum(len(answer.get("gaps", [])) for section in sections for answer in section["answers"]),
        },
    }


class _Context:
    def __init__(self, *, goal_report: dict[str, Any], interpretation: dict[str, Any]) -> None:
        self.goal_report = goal_report
        self.interpretation = interpretation
        self.outputs = dict(dict(goal_report.get("execution", {})).get("outputs", {}))
        self.project_report = dict(self.outputs.get("project_map_report", {}))
        self.summary = dict(self.project_report.get("summary", {}))
        self.answers = dict(self.project_report.get("answers", {}))
        self.scope = dict(self.answers.get("1_scope", {}))
        self.execution = dict(self.answers.get("2_execution", {}))
        self.capabilities = dict(self.answers.get("3_capabilities", {}))
        self.contracts = dict(self.answers.get("4_contracts_data", {}))
        self.errors = dict(self.answers.get("5_errors_state_repro", {}))
        self.readiness = dict(self.answers.get("6_runtime_extraction_readiness", {}))
        self.structure = dict(self.outputs.get("extract_python_structure", {}))
        self.insights = dict(self.structure.get("project_insights", {}))
        self.runtime_commands = dict(self.outputs.get("extract_runtime_commands", {}))
        self.architecture = dict(interpretation.get("architecture_synthesis", {}))
        self.tasks = list(interpretation.get("analysis_tasks", {}).get("tasks", []))
        self.knowledge_gap = interpretation.get("knowledge_gap")
        self.research_plan = interpretation.get("research_plan")
