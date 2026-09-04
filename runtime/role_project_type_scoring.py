"""Maturity scoring helpers for role/project-type evaluation."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any


def _role_scores(case: dict[str, Any], policy: dict[str, Any]) -> dict[str, dict[str, Any]]:
    score_payload = case.get("score") if isinstance(case.get("score"), dict) else {}
    candidates = [
        (case.get("role_scores"), "role_scores"),
        (dict(case.get("semantic_quality") or {}).get("role_scores"), "semantic_quality"),
        (score_payload.get("role_scores"), "score_role_scores"),
        (dict(score_payload.get("foundation_semantic_quality") or {}).get("role_scores"), "foundation_semantic_quality"),
        (dict(score_payload.get("foundation_semantic_quality") or {}).get("role_scores_10pt"), "foundation_semantic_quality"),
    ]
    result: dict[str, dict[str, Any]] = {}
    for values, source in candidates:
        if not isinstance(values, dict):
            continue
        for role_id, value in values.items():
            if (
                role_id in policy["roles"]
                and role_id not in result
                and isinstance(value, (int, float))
            ):
                result[str(role_id)] = {"raw_score": float(value), "score": float(value), "source": source}
    legacy = score_payload
    legacy_values = {
        "implementer": legacy.get("implementation_score"),
        "tester": legacy.get("qa_score"),
        "reviewer": legacy.get("qa_score"),
    }
    ceiling = float(policy["legacy_score_ceiling"])
    for role_id, value in legacy_values.items():
        if role_id in result or not isinstance(value, (int, float)):
            continue
        raw = float(value) * 10.0 if float(value) <= 1.0 else float(value)
        result[role_id] = {"raw_score": raw, "score": min(raw, ceiling), "source": "legacy_component_score"}
    return result


def _transformation_evidence_scope(
    *, case: dict[str, Any], classification: dict[str, Any]
) -> str:
    if not bool(dict(case.get("programmer_evidence") or {}).get("transformation_evaluated")):
        return "not_evaluated"
    archetype = str(classification.get("project_archetype") or "")
    if archetype.startswith("derived_") or archetype.endswith("_benchmark"):
        return "derived_transformation_benchmark"
    return "project_native"


def _cell(role_id: str, stratum: dict[str, Any], rows: list[dict[str, Any]], policy: dict[str, Any]) -> dict[str, Any]:
    applicable_roles = {str(value) for value in stratum.get("applicable_roles") or policy["roles"]}
    applicable = role_id in applicable_roles
    conditional = dict(policy.get("conditional_role_applicability") or {})
    if role_id in conditional:
        applicable = applicable and str(stratum["id"]) in {
            str(value) for value in conditional[role_id]
        }
    if not applicable:
        rows = []
    projects = sorted({str(row["project"]) for row in rows})
    blind_projects = sorted({str(row["project"]) for row in rows if row["blind"]})
    reports = sorted({str(row["report"]) for row in rows})
    transformation_projects = sorted({
        str(row["project"]) for row in rows if row.get("transformation_evaluated") is True
    })
    native_transformation_projects = sorted({
        str(row["project"])
        for row in rows
        if row.get("transformation_evaluated") is True
        and row.get("transformation_evidence_scope") == "project_native"
    })
    transformation_lineages = sorted({
        str(row["source_lineage"])
        for row in rows
        if row.get("transformation_evaluated") is True and row.get("source_lineage")
    })
    transformation_subtypes = sorted({
        str(row["project_subtype"])
        for row in rows
        if row.get("transformation_evaluated") is True and row.get("project_subtype")
    })
    thresholds = dict(policy["evidence_thresholds"])
    gaps = []
    if len(projects) < int(thresholds["minimum_cases"]):
        gaps.append("minimum_cases")
    if len(blind_projects) < int(thresholds["minimum_blind_cases"]):
        gaps.append("minimum_blind_cases")
    if len(reports) < int(thresholds["minimum_independent_reports"]):
        gaps.append("minimum_independent_reports")
    demonstration = dict(policy.get("demonstration_thresholds") or {})
    if role_id in set(demonstration.get("roles") or []):
        if len(transformation_projects) < int(demonstration.get("minimum_transformation_projects") or 0):
            gaps.append("minimum_transformation_projects")
        if len(native_transformation_projects) < int(
            demonstration.get("minimum_project_native_transformations") or 0
        ):
            gaps.append("minimum_project_native_transformations")
        if len(transformation_lineages) < int(demonstration.get("minimum_independent_lineages") or 0):
            gaps.append("minimum_independent_lineages")
        if len(transformation_subtypes) < int(demonstration.get("minimum_transformation_subtypes") or 0):
            gaps.append("minimum_transformation_subtypes")
    if stratum.get("maturity_allowed") is False:
        gaps.append("unclassified_archetype")
    scores = [float(row["score"]) for row in rows]
    worst = min(scores) if scores else None
    if not applicable:
        maturity = "not_applicable"
        gaps = []
    elif worst is None:
        maturity = "unmeasured"
    elif worst < float(policy["usable_score"]):
        maturity = "weak"
    elif worst >= float(policy["target_score"]) and not gaps:
        maturity = "mature"
    else:
        maturity = "usable"
    confidence = "not_applicable" if not applicable else "high" if not gaps else "medium" if len(projects) >= 3 and len(blind_projects) >= 1 else "low"
    risk_counts: dict[str, int] = defaultdict(int)
    for row in rows:
        for risk in row["risk_profiles"]:
            risk_counts[str(risk)] += 1
    return {
        "role_id": role_id,
        "project_stratum": str(stratum["id"]),
        "stratum_label": str(stratum.get("label") or stratum["id"]),
        "applicable": applicable,
        "maturity": maturity,
        "confidence": confidence,
        "score": round(worst, 2) if worst is not None else None,
        "average_score": round(sum(scores) / len(scores), 2) if scores else None,
        "project_count": len(projects),
        "blind_project_count": len(blind_projects),
        "independent_report_count": len(reports),
        "transformation_project_count": len(transformation_projects),
        "project_native_transformation_count": len(native_transformation_projects),
        "independent_transformation_lineage_count": len(transformation_lineages),
        "transformation_subtype_count": len(transformation_subtypes),
        "transformation_subtypes": transformation_subtypes,
        "transformation_evidence_scopes": sorted({
            str(row.get("transformation_evidence_scope"))
            for row in rows
            if row.get("transformation_evaluated") is True
        }),
        "score_scope": (
            "bounded_transformation_contracts"
            if role_id in set(demonstration.get("roles") or [])
            and transformation_projects
            and not native_transformation_projects
            else "project_type_evidence"
        ),
        "observation_count": len(rows),
        "evidence_gaps": gaps,
        "score_sources": sorted({str(row["score_source"]) for row in rows}),
        "classification_sources": sorted({str(row["classification_source"]) for row in rows}),
        "classification_conflict_count": sum(bool(row["classification_conflict"]) for row in rows),
        "project_archetypes": sorted({
            str(row["project_archetype"]) for row in rows if row.get("project_archetype")
        }),
        "contract_families": sorted({
            str(row["contract_family"]) for row in rows if row.get("contract_family")
        }),
        "risk_profile_counts": dict(sorted(risk_counts.items())),
        "projects": projects,
    }


def _role_summary(role_id: str, cells: list[dict[str, Any]]) -> dict[str, Any]:
    applicable = [row for row in cells if row["maturity"] != "not_applicable"]
    measured = [row for row in applicable if row["project_count"] > 0]
    scores = [float(row["score"]) for row in measured if row["score"] is not None]
    return {
        "score": round(min(scores), 2) if scores else None,
        "measured_strata": len(measured),
        "mature_strata": sum(row["maturity"] == "mature" for row in cells),
        "usable_strata": sum(row["maturity"] == "usable" for row in cells),
        "weak_strata": sum(row["maturity"] == "weak" for row in cells),
        "unmeasured_strata": sum(row["maturity"] == "unmeasured" for row in cells),
        "not_applicable_strata": sum(row["maturity"] == "not_applicable" for row in cells),
        "coverage": round(len(measured) / len(applicable), 4) if applicable else 0.0,
    }


def _heatmap(cells: list[dict[str, Any]], policy: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "project_stratum": stratum["id"],
            "label": stratum.get("label") or stratum["id"],
            "roles": {
                role: {
                    "score": next(row["score"] for row in cells if row["role_id"] == role and row["project_stratum"] == stratum["id"]),
                    "maturity": next(row["maturity"] for row in cells if row["role_id"] == role and row["project_stratum"] == stratum["id"]),
                    "confidence": next(row["confidence"] for row in cells if row["role_id"] == role and row["project_stratum"] == stratum["id"]),
                }
                for role in policy["roles"]
            },
        }
        for stratum in policy["strata"]
    ]


def _priority(cell: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    measured = cell["score"] is not None
    score = float(cell["score"]) if measured else 0.0
    target = _development_target(str(cell["project_stratum"]), policy)
    score_gap = max(0.0, target - score) if measured else 0.0
    evidence_penalty = 0.25 * len(cell["evidence_gaps"])
    impact = float(dict(policy.get("role_impact") or {}).get(cell["role_id"], 1.0))
    sample_signal = 1.0 + min(0.5, math.log1p(cell["project_count"]) / 10.0)
    current = dict(dict(policy.get("development_priority") or {}).get("current_lane") or {})
    current_strata = set(current.get("project_strata") or [])
    lane = "current" if cell["project_stratum"] in current_strata else "deferred"
    return {
        "role_id": cell["role_id"],
        "project_stratum": cell["project_stratum"],
        "score": cell["score"],
        "maturity": cell["maturity"],
        "project_count": cell["project_count"],
        "evidence_gaps": cell["evidence_gaps"],
        "development_lane": lane,
        "lane_order": 0 if lane == "current" else 1,
        "target_score": target,
        "priority_score": round((score_gap + evidence_penalty) * impact * sample_signal, 2),
    }


def _development_target(project_stratum: str, policy: dict[str, Any]) -> float:
    priority = dict(policy.get("development_priority") or {})
    for lane_name in ("current_lane", "deferred_lane"):
        lane = dict(priority.get(lane_name) or {})
        if project_stratum in set(lane.get("project_strata") or []):
            return float(lane.get("target_score") or policy["promotion_score"])
    return float(policy["promotion_score"])
