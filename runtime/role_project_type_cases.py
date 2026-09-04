"""Case extraction and source bookkeeping for role/project-type evaluation."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


def _project_development_evaluation_case(payload: dict[str, Any]) -> dict[str, Any]:
    recognition = dict(payload.get("recognition") or {})
    classification = dict(recognition.get("classification") or {})
    handoff = dict(payload.get("role_chain_handoff") or {})
    experiment = dict(payload.get("experiment") or {})
    reassessment = dict(payload.get("outcome_reassessment") or {})
    native = dict(experiment.get("project_native_verification") or {})
    issue = dict(dict(payload.get("decision") or {}).get("selected_issue") or {})
    validated = (
        payload.get("status") == "experiment_validated"
        and experiment.get("status") == "verified"
        and reassessment.get("status") == "validated"
        and native.get("status") == "passed"
    )
    role_scores: dict[str, float] = {}
    if recognition.get("status") == "recognized":
        role_scores["project_analyzer"] = 9.7
    if handoff.get("status") == "completed_aligned" and handoff.get("issue_target_aligned") is True:
        role_scores.update({"architect": 9.7, "spec_writer": 9.7})
    if validated:
        role_scores.update({"implementer": 9.8, "tester": 10.0, "reviewer": 9.8})
    failure_kinds = [str(value) for value in issue.get("failure_kinds") or [] if value]
    patch_kinds = [str(value) for value in experiment.get("patch_kinds") or [] if value]
    subtype = "+".join([*failure_kinds, *patch_kinds]) or "project_native_development"
    return {
        "project": payload.get("project"),
        "status": "passed" if validated else "failed",
        "project_stratum": classification.get("project_stratum"),
        "project_classification": classification,
        "project_subtype": subtype,
        "source_lineage": f"project_native_failure:{'+'.join(failure_kinds) or 'unknown'}",
        "role_scores": role_scores,
        "programmer_evidence": {
            "transformation_evaluated": validated,
            "verification_authority": native.get("authority"),
            "targeted_replay_status": dict(native.get("targeted_replay") or {}).get("status"),
            "regression_status": dict(native.get("regression_suite") or {}).get("status"),
        },
        "project_development_evidence": {
            "selected_target": experiment.get("selected_target"),
            "patch_kinds": patch_kinds,
            "source_project_unchanged": dict(experiment.get("source_invariant") or {}).get("unchanged"),
        },
    }


def _classification_debt(
    role_observations: Iterable[list[dict[str, Any]]],
) -> dict[str, Any]:
    projects: dict[str, dict[str, Any]] = {}
    for rows in role_observations:
        for row in rows:
            project = str(row.get("project") or "unknown-project")
            entry = projects.setdefault(project, defaultdict(set))
            entry["roles"].add(str(row.get("role_id") or ""))
            for field in ("project_archetype", "contract_family", "classification_source", "report"):
                value = row.get(field)
                if value:
                    entry[field].add(str(value))
            entry["risk_profiles"].update(str(value) for value in row.get("risk_profiles") or [])
            hypothesis = dict(row.get("unknown_archetype_evidence") or {})
            if hypothesis.get("hypothesis_id"):
                entry.setdefault("hypotheses", {})[str(hypothesis["hypothesis_id"])] = hypothesis

    items = []
    for project, entry in sorted(projects.items()):
        items.append({
            "project": project,
            "observed_roles": sorted(value for value in entry["roles"] if value),
            "project_archetypes": sorted(entry["project_archetype"]),
            "contract_families": sorted(entry["contract_family"]),
            "risk_profiles": sorted(entry["risk_profiles"]),
            "classification_sources": sorted(entry["classification_source"]),
            "reports": sorted(entry["report"]),
            "archetype_hypotheses": [
                entry["hypotheses"][key] for key in sorted(entry.get("hypotheses", {}))
            ],
            "reason": "no_configured_project_stratum_matched_authoritative_evidence",
            "next_action": "map_existing_stratum_or_add_validated_archetype",
        })
    return {
        "status": "needs_classification" if items else "clear",
        "count": len(items),
        "items": items,
    }


def _latest_foundation_reports(
    reports: list[tuple[int, Path, dict[str, Any]]],
) -> dict[str, str]:
    winners: dict[str, tuple[str, int, str]] = {}
    for order, resolved, payload in reports:
        if str(payload.get("artifact_type") or payload.get("kind") or "") != "RoleFoundationFieldTrialReport":
            continue
        generated_at = str(payload.get("generated_at") or "")
        for case in payload.get("cases", []):
            if not isinstance(case, dict):
                continue
            project = str(case.get("project") or case.get("name") or "")
            if not project:
                continue
            candidate = (generated_at, order, resolved.as_posix())
            if project not in winners or candidate[:2] > winners[project][:2]:
                winners[project] = candidate
    return {project: row[2] for project, row in winners.items()}


def _foundation_case_is_current(
    payload: dict[str, Any], case: dict[str, Any], report_id: str,
    winners: dict[str, str],
) -> bool:
    artifact_type = str(payload.get("artifact_type") or payload.get("kind") or "")
    if artifact_type != "RoleFoundationFieldTrialReport":
        return True
    project = str(case.get("project") or case.get("name") or "")
    return not project or winners.get(project) == report_id


def _case_with_loaded_artifacts(case: dict[str, Any], root: Path) -> dict[str, Any]:
    loaded = {}
    root_resolved = root.resolve()
    for key, value in dict(case.get("artifacts") or {}).items():
        row = dict(value or {}) if isinstance(value, dict) else {}
        path_value = row.get("path")
        if not path_value:
            loaded[key] = value
            continue
        path = Path(str(path_value)).resolve()
        try:
            path.relative_to(root_resolved)
            loaded[key] = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError, json.JSONDecodeError):
            loaded[key] = value
    return {**case, "artifacts": loaded}


def _resolved(root: Path, path: Path) -> Path:
    return (path if path.is_absolute() else root / path).resolve()
