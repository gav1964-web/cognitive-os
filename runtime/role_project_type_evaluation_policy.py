"""Policy loading for role/project-type evaluation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY_PATH = ROOT / "config" / "role_project_type_evaluation.json"


class RoleProjectTypeEvaluationError(RuntimeError):
    """Raised when role/project-type evaluation input or policy is invalid."""


def load_role_project_type_policy(path: str | Path | None = None) -> dict[str, Any]:
    source = Path(path) if path else DEFAULT_POLICY_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "role_project_type_evaluation.v1":
        raise RoleProjectTypeEvaluationError(
            "role project type policy must use schema_version role_project_type_evaluation.v1"
        )
    if not payload.get("roles") or not payload.get("strata"):
        raise RoleProjectTypeEvaluationError("role project type policy requires roles and strata")
    stratum_ids = [str(row.get("id") or "") for row in payload["strata"]]
    if len(stratum_ids) != len(set(stratum_ids)) or "unknown_new_archetype" not in stratum_ids:
        raise RoleProjectTypeEvaluationError("strata must be unique and include unknown_new_archetype")
    thresholds = dict(payload.get("evidence_thresholds") or {})
    if not all(int(thresholds.get(key) or 0) > 0 for key in (
        "minimum_cases", "minimum_blind_cases", "minimum_independent_reports"
    )):
        raise RoleProjectTypeEvaluationError("evidence_thresholds must contain positive minimums")
    return payload
