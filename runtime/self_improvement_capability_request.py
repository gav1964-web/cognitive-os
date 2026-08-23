"""Escalation artifacts for improvement gaps unsupported by registered plugins."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .knowledge_admission import capability_gap_report, load_kb_candidates
from .self_improvement_signatures import portable_failure_signature


def capability_development_requests(
    root: Path,
    training: list[dict[str, Any]],
    *,
    minimum_projects: int = 3,
    signature_normalization: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return repeated gaps that Cognitive OS cannot currently trial or promote."""
    observed = capability_gap_report(
        load_kb_candidates(root=root), min_observed_projects=minimum_projects
    )
    gaps = {str(row["gap_id"]): row for row in observed["gaps"]}
    unsupported = _unsupported_gap_ids(training)
    gap_requests = [
        _request(gaps[gap_id])
        for gap_id in sorted(unsupported)
        if gap_id in gaps and gaps[gap_id]["status"] == "research_candidate"
    ]
    return [
        *gap_requests,
        *_parameter_search_requests(training, minimum_projects),
        *_structural_discriminator_requests(
            training, minimum_projects, signature_normalization or {}
        ),
    ]


def _unsupported_gap_ids(training: list[dict[str, Any]]) -> set[str]:
    result = set()
    for report in training:
        conclusion = dict(report.get("trial_conclusion") or {})
        if conclusion.get("recommended_change_type") != "staged_capability_gap":
            continue
        cycle = dict(report.get("improvement_plugin_cycle") or {})
        attempts = list(cycle.get("attempts") or [])
        supported = any(
            row.get("status") in {"trial_passed", "promoted"}
            for row in attempts if isinstance(row, dict)
        )
        if supported:
            continue
        diagnosis = dict(report.get("diagnosis") or {})
        failure_class = str(diagnosis.get("failure_class") or "unknown")
        hypothesis = str(conclusion.get("next_hypothesis") or "unknown_foundation_capability")
        signature = str(conclusion.get("capability_signature") or "unclassified")
        result.add(f"{failure_class}:{hypothesis}:{signature}")
    return result


def _request(gap: dict[str, Any]) -> dict[str, Any]:
    gap_id = str(gap["gap_id"])
    digest = hashlib.sha256(gap_id.encode("utf-8")).hexdigest()[:12]
    capability = (
        "bounded_executable_target_discovery_or_sandbox_adapter"
        if ":no_viable_executable_candidate:" in gap_id
        else "new_bounded_improvement_plugin"
    )
    return {
        "artifact_type": "CapabilityDevelopmentRequest",
        "request_id": f"cdr_{digest}",
        "status": "implementation_required",
        "gap_id": gap_id,
        "label": gap.get("label"),
        "observed_projects": sorted(gap.get("projects") or []),
        "role_scope": sorted(gap.get("role_scope") or []),
        "missing_capability": capability,
        "required_plugin_contract": {
            "input": "FailurePacket plus repeated independent project evidence",
            "output": "bounded shadow-trial candidate with measurable corpus effect",
            "promotion_gates": [
                "independent_holdout",
                "no_role_regression",
                "source_project_unchanged",
                "sandbox_execution_only",
            ],
        },
        "intervention_scope": "implement_or_repair_self_improvement_plugin_only",
        "forbidden": [
            "manual_project_repair",
            "evaluation_threshold_change",
            "unverified_kb_promotion",
        ],
    }


def _parameter_search_requests(
    training: list[dict[str, Any]], minimum_projects: int
) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for report in training:
        conclusion = dict(report.get("trial_conclusion") or {})
        if conclusion.get("recommended_change_type") != "none":
            continue
        if conclusion.get("next_hypothesis") != "continue_bounded_parameter_search":
            continue
        if not report.get("knowledge_candidate_path") or _has_supported_plugin(report):
            continue
        failure_class = str(dict(report.get("diagnosis") or {}).get("failure_class") or "unknown")
        signature = _parameter_search_signature(report)
        group_key = f"{failure_class}:{signature}"
        group = groups.setdefault(group_key, {
            "failure_class": failure_class, "signature": signature,
            "projects": set(), "role_scope": set(), "strategy_plugin_attempted": False,
        })
        group["projects"].add(str(report.get("project") or ""))
        group["role_scope"].update(dict(report.get("diagnosis") or {}).get("target_roles") or [])
        group["strategy_plugin_attempted"] |= _strategy_plugin_attempted(report)
    requests = []
    for _, group in sorted(groups.items()):
        failure_class = str(group["failure_class"])
        signature = str(group["signature"])
        projects = sorted(project for project in group["projects"] if project)
        if len(projects) < minimum_projects:
            continue
        gap = {
            "gap_id": f"training_search:{failure_class}:{signature}:continue_bounded_parameter_search",
            "label": f"Bounded parameter search exhausted for {failure_class} ({signature})",
            "projects": projects,
            "role_scope": sorted(group["role_scope"]),
        }
        request = _request(gap)
        if failure_class != "executable_sample_contract":
            request["missing_capability"] = "new_bounded_improvement_plugin"
        else:
            request["missing_capability"] = (
                "bounded_parameter_strategy_extension"
                if group["strategy_plugin_attempted"] else "bounded_parameter_strategy_plugin"
            )
        requests.append(request)
    return requests


def _parameter_search_signature(report: dict[str, Any]) -> str:
    baseline = dict(report.get("baseline") or {})
    downstream = dict(baseline.get("downstream_evidence") or {})
    quality = dict(baseline.get("selected_candidate_quality") or {})
    structural = dict(quality.get("structural_evidence") or {})
    effects = ",".join(sorted(str(value) for value in structural.get("observed_side_effects") or []))
    return "|".join([
        str(downstream.get("reason") or downstream.get("acceptance_signal") or "unclassified"),
        effects or "pure", str(structural.get("output_inference_basis") or "unknown"),
    ])


def _has_supported_plugin(report: dict[str, Any]) -> bool:
    cycle = dict(report.get("improvement_plugin_cycle") or {})
    return any(
        row.get("status") in {"trial_passed", "promoted"}
        for row in list(cycle.get("attempts") or []) if isinstance(row, dict)
    )


def _strategy_plugin_attempted(report: dict[str, Any]) -> bool:
    if dict(report.get("diagnosis") or {}).get("failure_class") != "executable_sample_contract":
        return False
    cycle = dict(report.get("improvement_plugin_cycle") or {})
    return any(
        row.get("plugin_id") == "bounded_parameter_strategy"
        for row in list(cycle.get("attempts") or []) if isinstance(row, dict)
    )


def _structural_discriminator_requests(
    training: list[dict[str, Any]], minimum_projects: int,
    normalization: dict[str, Any],
) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for report in training:
        if not report.get("knowledge_candidate_path") or _has_supported_plugin(report):
            continue
        failure_class = str(dict(report.get("diagnosis") or {}).get("failure_class") or "unknown")
        if failure_class == "unknown":
            continue
        signature = portable_failure_signature(report, normalization)
        key = f"{failure_class}:{signature}"
        group = groups.setdefault(key, {
            "failure_class": failure_class, "signature": signature,
            "projects": set(), "role_scope": set(),
            "unresolved_selections": 0, "blocked_discriminators": 0,
        })
        group["projects"].add(str(report.get("project") or ""))
        group["role_scope"].update(dict(report.get("diagnosis") or {}).get("target_roles") or [])
        cycle = dict(report.get("improvement_plugin_cycle") or {})
        selection_attempts = [
            row for row in list(cycle.get("attempts") or [])
            if isinstance(row, dict) and row.get("plugin_id") == "candidate_selection_admission"
        ]
        unresolved_reasons = {"measured_challenger_missing", "no_structural_discriminator"}
        if any(row.get("reason") in unresolved_reasons for row in selection_attempts):
            group["unresolved_selections"] += 1
        if any(row.get("reason") == "no_structural_discriminator" for row in selection_attempts):
            group["blocked_discriminators"] += 1
    requests = []
    for group in groups.values():
        projects = sorted(project for project in group["projects"] if project)
        if (
            len(projects) < minimum_projects
            or int(group["unresolved_selections"]) < minimum_projects
            or int(group["blocked_discriminators"]) < 1
        ):
            continue
        gap = {
            "gap_id": (
                f"training_search:{group['failure_class']}:{group['signature']}:"
                "structural_discriminator_missing"
            ),
            "label": f"Structural discriminator missing for {group['signature']}",
            "projects": projects,
            "role_scope": sorted(group["role_scope"]),
        }
        request = _request(gap)
        request["missing_capability"] = "candidate_selection_discriminator_plugin"
        requests.append(request)
    return requests
