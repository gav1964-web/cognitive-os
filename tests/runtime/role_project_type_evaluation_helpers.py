import json
from pathlib import Path

from runtime.role_project_type_evaluation import (
    build_role_project_type_evaluation,
    classify_project_case,
    load_role_project_type_policy,
    render_role_project_type_markdown,
    _project_development_evaluation_case,
)














































































def _case(project: str, analyzer: float, implementer: float) -> dict:
    return {
        "project": project,
        "project_classification": {
            "schema_version": "role_project_classification.v1",
            "project_stratum": "cli_local_tool",
            "risk_profiles": ["deterministic"],
        },
        "role_scores": {
            "project_analyzer": analyzer,
            "implementer": implementer,
        },
    }


def _unknown_case(project: str) -> dict:
    return {
        "project": project,
        "project_classification": {
            "schema_version": "role_project_classification.v1",
            "project_stratum": "unknown_new_archetype",
        },
        "role_scores": {"project_analyzer": 10.0},
    }


def _cell(report: dict, role_id: str, stratum: str) -> dict:
    return next(
        row for row in report["cells"]
        if row["role_id"] == role_id and row["project_stratum"] == stratum
    )

__all__ = [name for name in globals() if not name.startswith("__")]
