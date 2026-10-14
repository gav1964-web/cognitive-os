"""Compare protected mature role/type cells across evaluation reports."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def build_role_evaluation_regression(
    baseline: dict[str, Any], candidate: dict[str, Any]
) -> dict[str, Any]:
    protected = list(
        dict(baseline.get("known_strata_regression_baseline") or {}).get(
            "protected_cells"
        )
        or []
    )
    cells = {
        (str(row.get("role_id")), str(row.get("project_stratum"))): row
        for row in candidate.get("cells") or []
        if isinstance(row, dict)
    }
    regressions = []
    for expected in protected:
        identity = (
            str(expected.get("role_id")),
            str(expected.get("project_stratum")),
        )
        actual = dict(cells.get(identity) or {})
        expected_score = expected.get("score")
        actual_score = actual.get("score")
        if (
            not isinstance(actual_score, (int, float))
            or not isinstance(expected_score, (int, float))
            or float(actual_score) < float(expected_score)
            or actual.get("maturity") != "mature"
        ):
            regressions.append({
                "role_id": identity[0],
                "project_stratum": identity[1],
                "expected_score": expected_score,
                "actual_score": actual_score,
                "actual_maturity": actual.get("maturity"),
            })
    checks = {
        "baseline_has_protected_cells": bool(protected),
        "all_protected_cells_present": len(protected) == len(protected) - sum(
            not cells.get((str(row.get("role_id")), str(row.get("project_stratum"))))
            for row in protected
        ),
        "no_score_or_maturity_regression": not regressions,
    }
    body = {
        "artifact_type": "RoleEvaluationRegression",
        "schema_version": "role_evaluation_regression.v1",
        "status": "passed" if all(checks.values()) else "failed",
        "protected_cell_count": len(protected),
        "candidate_protected_cell_count": int(
            dict(candidate.get("known_strata_regression_baseline") or {}).get(
                "protected_cell_count"
            )
            or 0
        ),
        "regression_count": len(regressions),
        "regressions": regressions,
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
    }
    return {**body, "regression_digest": _digest(body)}


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
