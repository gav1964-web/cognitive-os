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
    semantic = dict(
        payload.get("role_semantic_quality")
        or payload.get("foundation_semantic_quality")
        or {}
    )
    semantic_scores = dict(semantic.get("role_scores") or {})
    native = dict(experiment.get("project_native_verification") or {})
    issue = dict(dict(payload.get("decision") or {}).get("selected_issue") or {})
    validated = (
        payload.get("status") == "experiment_validated"
        and experiment.get("status") == "verified"
        and reassessment.get("status") == "validated"
        and native.get("status") == "passed"
    )
    role_scores: dict[str, float] = {}
    if (
        recognition.get("status") == "recognized"
        and handoff.get("status") == "completed_aligned"
        and handoff.get("issue_target_aligned") is True
        and semantic.get("status") in {"ok", "passed"}
    ):
        for role_id in ("project_analyzer", "architect", "spec_writer"):
            value = semantic_scores.get(role_id)
            if isinstance(value, (int, float)):
                role_scores[role_id] = float(value)
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


def _github_full_chain_evaluation_case(case: dict[str, Any]) -> dict[str, Any]:
    classification = dict(case.get("project_classification") or {})
    recognition = dict(case.get("project_recognition") or {})
    artifacts = dict(case.get("artifact_status") or {})
    executor = dict(case.get("executor") or {})
    stub = dict(case.get("generated_function_stub_admission") or {})
    targets = dict(case.get("target_chain") or {})
    semantic = dict(case.get("role_semantic_quality") or {})
    semantic_scores = dict(semantic.get("role_scores") or {})
    target_values = [
        targets.get(name)
        for name in ("spec_target", "implementation_target", "test_target", "review_target")
    ]
    recognized = recognition.get("status") == "recognized"
    chain_ready = (
        case.get("status") == "ok"
        and not case.get("failed_checks")
        and all(artifacts.get(name) for name in (
            "architecture_decision", "technical_spec", "implementation_plan",
            "test_plan", "review_findings",
        ))
        and bool(target_values[0])
        and len(set(target_values)) == 1
        and case.get("conformance_status") == "passed"
        and int(case.get("contract_violations") or 0) == 0
        and int(case.get("architecture_drift") or 0) == 0
    )
    execution_ready = (
        chain_ready
        and executor.get("executor_status") == "ok"
        and executor.get("executable_acceptance") == "passed"
        and int(executor.get("callable_harness_count") or 0) > 0
        and executor.get("source_code_changes") is False
        and stub.get("status") == "passed"
    )
    role_scores: dict[str, float] = {}
    if recognized and chain_ready and semantic.get("status") == "passed":
        for role_id in ("project_analyzer", "architect", "spec_writer"):
            value = semantic_scores.get(role_id)
            if isinstance(value, (int, float)):
                role_scores[role_id] = float(value)
    if execution_ready:
        role_scores.update({"implementer": 9.8, "tester": 10.0, "reviewer": 9.8})
    project = str(case.get("project") or "unknown-project")
    return {
        **case,
        "project": project,
        "project_stratum": classification.get("project_stratum"),
        "project_classification": classification,
        "source_lineage": f"github_owner:{project.split('__', 1)[0].lower()}",
        "role_scores": role_scores,
        "programmer_evidence": {
            "transformation_evaluated": False,
            "verification_authority": "github_full_chain_executable_acceptance",
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
