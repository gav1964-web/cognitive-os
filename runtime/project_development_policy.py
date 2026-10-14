"""Policy loading for project development."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "config" / "project_development_policy.json"


class ProjectDevelopmentPolicyError(RuntimeError):
    """Raised when the project-development policy is incomplete."""


def load_project_development_policy(path: str | None = None) -> dict[str, Any]:
    payload = json.loads(Path(path or DEFAULT_POLICY).read_text(encoding="utf-8"))
    if payload.get("schema_version") != "project_development_policy.v1":
        raise ProjectDevelopmentPolicyError("project development policy must use schema_version project_development_policy.v1")
    for field in (
        "selection", "issue_rules", "option_templates", "outcome_policy",
        "execution_policy", "memory_policy", "feedback_policy",
        "verified_issue_reducers",
    ):
        if not payload.get(field):
            raise ProjectDevelopmentPolicyError(f"project development policy missing {field}")
    return payload
