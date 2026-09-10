"""Evaluate frozen framework/plugin holdout evidence without applying promotion."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .framework_plugin_readiness import REQUIRED_ROLES
from .framework_plugin_role_semantics import artifact_digest


def evaluate_framework_plugin_holdout(
    *,
    selection: dict[str, Any],
    evaluation: dict[str, Any],
    holdout_reports: list[dict[str, Any]],
    report_digests: dict[str, str],
    stub_audit: dict[str, Any],
    role_regression: dict[str, Any],
    input_digests: dict[str, str],
    target_score: float = 9.7,
) -> dict[str, Any]:
    cells = {
        str(row.get("role_id")): dict(row)
        for row in evaluation.get("cells") or []
        if row.get("project_stratum") == "framework_plugin_build"
    }
    holdout = [dict(row) for row in selection.get("holdout") or []]
    selected_projects = {str(row.get("project")) for row in holdout}
    report_projects = {
        str(case.get("project"))
        for report in holdout_reports
        for case in report.get("cases") or []
        if isinstance(case, dict)
    }
    role_cells_ready = all(
        role in cells
        and isinstance(cells[role].get("score"), (int, float))
        and float(cells[role]["score"]) >= target_score
        and cells[role].get("maturity") == "mature"
        and not cells[role].get("evidence_gaps")
        and int(cells[role].get("blind_project_count") or 0) >= 3
        for role in REQUIRED_ROLES
    )
    chain_ready = all(_report_chain_ready(report) for report in holdout_reports)
    semantic_ready = all(_report_semantics_ready(report) for report in holdout_reports)
    artifacts_auditable = all(_report_artifacts_auditable(report) for report in holdout_reports)
    semantic_cases = [
        case
        for report in holdout_reports
        for case in report.get("cases") or []
        if isinstance(case, dict)
    ]
    development_evaluated = bool(semantic_cases) and all(
        dict(case.get("role_semantic_quality") or {}).get("development_change_evaluated")
        is True
        for case in semantic_cases
    )
    audited = dict(stub_audit.get("report_digests") or {})
    checks = {
        "selection_frozen_and_complete": selection.get("status") == "local_corpus_sufficient"
        and len(selection.get("acquisition") or []) >= 3
        and len(holdout) >= 3,
        "independent_holdout": len(selected_projects) >= 3
        and len({row.get("owner") for row in holdout}) == len(holdout),
        "lineage_disjoint": dict(selection.get("checks") or {}).get("owner_disjoint") is True
        and dict(selection.get("checks") or {}).get("content_disjoint") is True,
        "holdout_reports_match_selection": selected_projects == report_projects
        and len(holdout_reports) == len(holdout),
        "role_cells_ready": role_cells_ready,
        "no_role_regression": role_regression.get("status") == "passed"
        and int(role_regression.get("regression_count") or 0) == 0,
        "role_chain_continuity": chain_ready,
        "semantic_role_quality": semantic_ready,
        "role_artifacts_auditable": artifacts_auditable,
        "project_development_evaluated": development_evaluated,
        "generated_stub_gate": stub_audit.get("status") == "passed"
        and int(stub_audit.get("generated_stub_count") or 0) == 0
        and audited == report_digests,
        "inputs_digest_bound": len(input_digests) >= 4 + len(holdout_reports)
        and all(str(value).startswith("sha256:") for value in input_digests.values()),
    }
    lineages = {str(row.get("owner")) for row in holdout if row.get("owner")}
    semantic_holdout_scores = _semantic_holdout_scores(holdout_reports)
    matrix_scores = {
        role: cells.get(role, {}).get("score") for role in REQUIRED_ROLES
    }
    body = {
        "artifact_type": "FrameworkPluginHoldoutEvidence",
        "schema_version": "framework_plugin_holdout_evidence.v2",
        "status": "passed" if all(checks.values()) else "evidence_required",
        "target_score": target_score,
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "generated_stub_count": int(stub_audit.get("generated_stub_count") or 0),
        "holdout_provenance": {
            "selection_digest": selection.get("selection_digest"),
            "case_count": len(report_projects),
            "source_lineages": len(lineages),
            "source_report_count": len(holdout_reports),
            "owners": sorted(lineages),
        },
        "role_scores": semantic_holdout_scores,
        "matrix_role_scores": matrix_scores,
        "input_digests": dict(sorted(input_digests.items())),
        "source_apply": False,
        "promotion_applied": False,
    }
    return {**body, "evidence_digest": _digest(body)}


def _report_chain_ready(report: dict[str, Any]) -> bool:
    if report.get("status") != "ok":
        return False
    for case in report.get("cases") or []:
        if not isinstance(case, dict) or case.get("status") != "ok" or case.get("failed_checks"):
            return False
        executor = dict(case.get("executor") or {})
        stub = dict(case.get("generated_function_stub_admission") or {})
        if not (
            executor.get("executor_status") == "ok"
            and executor.get("executable_acceptance") == "passed"
            and int(executor.get("callable_harness_count") or 0) > 0
            and stub.get("status") == "passed"
        ):
            return False
    return True


def _report_semantics_ready(report: dict[str, Any]) -> bool:
    cases = [case for case in report.get("cases") or [] if isinstance(case, dict)]
    return bool(cases) and all(
        dict(case.get("role_semantic_quality") or {}).get("status") == "passed"
        and all(
            isinstance(dict(case.get("role_semantic_quality") or {}).get("role_scores", {}).get(role), (int, float))
            and float(dict(case.get("role_semantic_quality") or {}).get("role_scores", {}).get(role)) >= 9.7
            for role in ("project_analyzer", "architect", "spec_writer")
        )
        for case in cases
    )


def _report_artifacts_auditable(report: dict[str, Any]) -> bool:
    cases = [case for case in report.get("cases") or [] if isinstance(case, dict)]
    for case in cases:
        artifacts = dict(case.get("role_artifacts") or {})
        digests = dict(case.get("role_artifact_digests") or {})
        required = {"project_map_report", "architecture_decision", "technical_spec"}
        if not required.issubset(artifacts) or not required.issubset(digests):
            return False
        if any(digests[name] != artifact_digest(dict(artifacts[name])) for name in required):
            return False
    return bool(cases)


def _semantic_holdout_scores(reports: list[dict[str, Any]]) -> dict[str, float | None]:
    result: dict[str, float | None] = {}
    for role in REQUIRED_ROLES:
        values = [
            float(value)
            for report in reports
            for case in report.get("cases") or []
            if isinstance(case, dict)
            for value in [dict(case.get("role_semantic_quality") or {}).get("role_scores", {}).get(role)]
            if isinstance(value, (int, float))
        ]
        result[role] = round(min(values), 2) if values else None
    return result


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
