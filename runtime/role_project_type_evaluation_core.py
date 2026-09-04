"""Report assembly for role/project-type evaluation."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from .role_project_type_cases import (
    _case_with_loaded_artifacts,
    _classification_debt,
    _foundation_case_is_current,
    _latest_foundation_reports,
    _project_development_evaluation_case,
    _resolved,
)
from .role_project_type_classification import classify_project_case
from .role_project_type_evaluation_policy import load_role_project_type_policy
from .role_project_type_scoring import (
    _cell,
    _development_target,
    _heatmap,
    _priority,
    _role_scores,
    _role_summary,
    _transformation_evidence_scope,
)
from .unknown_project_lifecycle import (
    build_known_strata_regression_baseline,
    build_unknown_project_lifecycle,
)


def build_role_project_type_evaluation(
    *,
    root: Path,
    report_paths: Iterable[Path],
    blind_report_paths: Iterable[Path] | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = policy or load_role_project_type_policy()
    blind = {_resolved(root, path) for path in (blind_report_paths or [])}
    sources = []
    observations: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    classification_by_project: dict[str, dict[str, Any]] = {}
    loaded_reports = []
    for order, path in enumerate(report_paths):
        resolved = _resolved(root, path)
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        loaded_reports.append((order, resolved, payload))
    foundation_winners = _latest_foundation_reports(loaded_reports)
    for _, resolved, payload in loaded_reports:
        report_id = resolved.as_posix()
        source_lineage = str(payload.get("source_lineage") or "")
        is_blind = resolved in blind
        cases = [dict(row) for row in payload.get("cases", []) if isinstance(row, dict)]
        if payload.get("artifact_type") == "ProjectDevelopmentRun":
            cases = [_project_development_evaluation_case(payload)]
        effective_cases = [
            case for case in cases
            if _foundation_case_is_current(payload, case, report_id, foundation_winners)
        ]
        sources.append({
            "path": report_id,
            "artifact_type": payload.get("artifact_type") or payload.get("kind"),
            "case_count": len(cases),
            "effective_case_count": len(effective_cases),
            "blind": is_blind,
        })
        for index, case in enumerate(effective_cases):
            if case.get("status") == "out_of_scope":
                continue
            expanded_case = _case_with_loaded_artifacts(case, root)
            project = str(case.get("project") or case.get("name") or f"case-{index + 1}")
            classification = classify_project_case(expanded_case, policy=config)
            if classification["project_stratum"] == "unknown_new_archetype" and project in classification_by_project:
                classification = classification_by_project[project]
            elif classification["project_stratum"] != "unknown_new_archetype":
                classification_by_project[project] = classification
            scores = _role_scores(case, config)
            for role_id, score in scores.items():
                observations[(role_id, classification["project_stratum"])].append({
                    "project": project,
                    "role_id": role_id,
                    "report": report_id,
                    "source_lineage": str(case.get("source_lineage") or source_lineage),
                    "blind": is_blind,
                    "score": score["score"],
                    "raw_score": score["raw_score"],
                    "score_source": score["source"],
                    "risk_profiles": classification["risk_profiles"],
                    "project_archetype": classification["project_archetype"],
                    "contract_family": classification["contract_family"],
                    "project_subtype": classification.get("project_subtype"),
                    "classification_source": classification["classification_source"],
                    "classification_conflict": classification["classification_conflict"],
                    "unknown_archetype_evidence": dict(case.get("unknown_archetype_evidence") or {}),
                    "transformation_evaluated": bool(
                        dict(case.get("programmer_evidence") or {}).get("transformation_evaluated")
                    ),
                    "transformation_evidence_scope": _transformation_evidence_scope(
                        case=case,
                        classification=classification,
                    ),
                })

    cells = []
    for stratum in config["strata"]:
        for role_id in config["roles"]:
            cells.append(_cell(role_id, dict(stratum), observations.get((role_id, stratum["id"]), []), config))
    role_summary = {
        role_id: _role_summary(role_id, [row for row in cells if row["role_id"] == role_id])
        for role_id in config["roles"]
    }
    priorities = sorted(
        (
            _priority(row, config)
            for row in cells
            if row["maturity"] != "not_applicable"
            and row["project_stratum"] != "unknown_new_archetype"
            and (
                row["maturity"] != "mature"
                or float(row.get("score") or 0.0) < _development_target(row["project_stratum"], config)
            )
        ),
        key=lambda row: (
            row["lane_order"], -row["priority_score"], row["role_id"], row["project_stratum"]
        ),
    )
    classification_debt = _classification_debt(
        observations.get((role_id, "unknown_new_archetype"), [])
        for role_id in config["roles"]
    )
    unknown_lifecycle = build_unknown_project_lifecycle(classification_debt, policy=config)
    regression_baseline = build_known_strata_regression_baseline(cells)
    return {
        "artifact_type": "RoleProjectTypeEvaluationReport",
        "schema_version": "role_project_type_evaluation_report.v1",
        "status": "ok",
        "maturity_status": "needs_work" if priorities or classification_debt["items"] else "mature",
        "target_score": float(config["target_score"]),
        "promotion_score": float(config["promotion_score"]),
        "sources": sources,
        "summary": {
            "report_count": len(sources),
            "observation_count": sum(len(rows) for rows in observations.values()),
            "measured_cell_count": sum(row["project_count"] > 0 for row in cells),
            "mature_cell_count": sum(row["maturity"] == "mature" for row in cells),
            "weak_cell_count": sum(row["maturity"] == "weak" for row in cells),
            "unmeasured_cell_count": sum(row["maturity"] == "unmeasured" for row in cells),
            "not_applicable_cell_count": sum(row["maturity"] == "not_applicable" for row in cells),
            "classification_debt_count": classification_debt["count"],
            "unknown_intake_count": unknown_lifecycle["intake_count"],
            "protected_mature_cell_count": regression_baseline["protected_cell_count"],
        },
        "roles": role_summary,
        "heatmap": _heatmap(cells, config),
        "cells": cells,
        "priority_queue": priorities[:30],
        "classification_debt": classification_debt,
        "unknown_project_lifecycle": unknown_lifecycle,
        "known_strata_regression_baseline": regression_baseline,
    }
