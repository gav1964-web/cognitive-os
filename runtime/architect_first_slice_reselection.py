"""Architect-owned expansion of a rejected first-slice candidate window."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .architect_candidate_quality import contract_quality
from .architect_semantic_admission import (
    semantic_threshold_satisfied as _semantic_threshold_satisfied,
)
from .architecture_target_priority import architecture_contract_has_priority, architecture_target_score
from .first_slice_viability import first_slice_viability
from .project_probe_env import declared_package_satisfies_module, declared_project_packages
from .promoted_candidate_selection_policies import apply_selection_policies, selected_policy_ids, selection_request_with_candidate
from .role_source_context import build_source_context
from .source_target_policy import is_context_only_implementation_target, is_protocol_dunder_target
from .spec_writer_target_binding import standalone_target_eligibility
from .technical_spec_policy import load_technical_spec_policy
from .architect_reselection_decision import (
    attach_outcome as _attach_outcome,
    revised_architecture_decision as _revised_architecture_decision,
)


def reselect_architecture_first_slice(
    *,
    architecture_decision: dict[str, Any],
    technical_spec: dict[str, Any],
    project_report: dict[str, Any],
    iteration: int,
) -> dict[str, Any]:
    request = dict(technical_spec.get("first_slice_reselection_request") or {})
    if request.get("status") != "required":
        return {"status": "not_required", "architecture_decision": architecture_decision}
    policy = dict(load_technical_spec_policy().get("first_slice_reselection") or {})
    sources = _expanded_candidate_sources(project_report, architecture_decision, policy)
    sources = _domain_aligned_sources(sources, architecture_decision, policy)
    project_root = str(
        architecture_decision.get("project")
        or dict(project_report.get("summary") or {}).get("root")
        or project_report.get("root")
        or ""
    )
    expanded_context = build_source_context(
        project_root=project_root,
        project_report=project_report,
        sources=sources,
        function_scoped_dependencies=True,
    )
    sources = _qualify_ambiguous_method_sources(sources, expanded_context)
    missing_context = [source for source in sources if source not in expanded_context]
    if missing_context:
        expanded_context.update(build_source_context(
            project_root=project_root,
            project_report=project_report,
            sources=missing_context,
            function_scoped_dependencies=True,
        ))
    ready = [source for source in sources if _environment_ready_callable(expanded_context.get(source))]
    declared = declared_project_packages(Path(project_root)) if project_root else set()
    eligible = [
        source
        for source in sources
        if _environment_ready_callable(expanded_context.get(source))
        or _declared_dependency_callable(expanded_context.get(source), declared, policy)
    ]
    rejected_primary = _previous_primary_targets(architecture_decision)
    eligible = [source for source in eligible if source not in rejected_primary]
    selected, viability = _viable_candidates(
        eligible,
        expanded_context,
        architecture_decision,
        limit=max(1, int(policy.get("selected_target_limit") or 8)),
        minimum_semantic_score=int(
            dict(request.get("blocking_evidence") or {}).get("minimum_semantic_score")
            or (
                policy.get("minimum_semantic_score")
                if request.get("trigger") == "executable_acceptance_rejected"
                else 0
            )
            or 0
        ),
        selection_request=selection_request_with_candidate(request, expanded_context.get(str(request.get("current_target") or ""))),
    )
    selection_policy_ids = selected_policy_ids(viability, selected)
    _mark_manifest_declared_context(selected, expanded_context, declared, policy)
    evidence = {
        "artifact_type": "FirstSliceReselectionOutcome",
        "iteration": iteration,
        "status": "selected" if selected else "exhausted",
        "trigger": request.get("trigger"),
        "expanded_candidate_count": len(sources),
        "environment_ready_candidate_count": len(ready),
        "declared_dependency_candidate_count": len(set(eligible) - set(ready)),
        "viability_deferred_candidate_count": sum(
            str(row.get("target") or "") in set(eligible)
            and not row.get("viability_eligible") and not row.get("selection_policy_ids")
            for row in viability
        ),
        "semantic_qualified_candidate_count": len(selected),
        "candidate_viability": viability,
        "selected_targets": selected,
        "selection_policy_ids": selection_policy_ids,
        "authority": "architect",
        "source": "ProjectMapReport expanded candidate evidence",
    }
    if not selected:
        return {
            "status": "exhausted",
            "architecture_decision": _attach_outcome(architecture_decision, evidence),
            "outcome": evidence,
        }
    revised = _revised_architecture_decision(
        architecture_decision,
        project_report=project_report,
        expanded_context=expanded_context,
        selected_targets=selected,
        outcome=evidence,
    )
    return {"status": "selected", "architecture_decision": revised, "outcome": evidence}

def _expanded_candidate_sources(
    project_report: dict[str, Any],
    architecture_decision: dict[str, Any],
    policy: dict[str, Any],
) -> list[str]:
    answers = dict(project_report.get("answers") or {})
    capabilities = dict(answers.get("3_capabilities") or {})
    readiness = dict(answers.get("6_runtime_extraction_readiness") or {})
    plan = dict(readiness.get("minimal_extraction_plan") or {})
    enabled = {str(item) for item in list(policy.get("candidate_sources") or [])}
    sources: list[str] = []
    for key in ("pure_transforms", "atomic_reusable_capabilities", "too_broad_functions"):
        if key in enabled:
            sources.extend(_row_sources(capabilities.get(key)))
    for key in ("process_boundary_candidates", "mixed_responsibility_functions", "hidden_orchestrators"):
        if key in enabled:
            sources.extend(_row_sources(readiness.get(key)))
    if "project_callable_inventory" in enabled:
        sources.extend(str(item) for item in list(project_report.get("reselection_candidate_inventory") or []))
    if "analysis_tasks" in enabled:
        analysis_tasks = project_report.get("analysis_tasks")
        task_rows = dict(analysis_tasks).get("tasks") if isinstance(analysis_tasks, dict) else analysis_tasks
        sources.extend(str(row.get("target") or "") for row in _rows(task_rows))
    if "dataflows" in enabled:
        sources.extend(str(row.get("entrypoint") or "") for row in _rows(readiness.get("dataflows")))
    if "minimal_extraction_plan" in enabled:
        sources.extend(_row_sources(plan.get("capabilities_to_extract")))
    sources.extend(str(item) for item in dict(architecture_decision.get("source_context") or {}))
    decision_context = dict(project_report.get("project_development_context") or {})
    if decision_context.get("authority") == "ProjectDevelopmentDecision":
        allowed = [str(source) for source in decision_context.get("allowed_targets") or []]
        sources = [*allowed, *(source for source in sources if source in set(allowed))]
    limit = max(1, int(policy.get("expanded_candidate_limit") or 64))
    return list(dict.fromkeys(
        source
        for source in sources
        if ".py:" in source
        and not is_context_only_implementation_target(source)
        and not is_protocol_dunder_target(source)
    ))[:limit]


def _domain_aligned_sources(
    sources: list[str], architecture_decision: dict[str, Any], policy: dict[str, Any]
) -> list[str]:
    first_slice = dict(architecture_decision.get("first_slice_contract") or {})
    knowledge_rule = str(first_slice.get("knowledge_rule") or "")
    tokens_by_rule = dict(policy.get("domain_candidate_required_any") or {})
    tokens = [str(item).lower() for item in list(tokens_by_rule.get(knowledge_rule) or [])]
    if not tokens:
        return sources
    aligned = [source for source in sources if any(token in source.lower() for token in tokens)]
    return aligned or sources

def _previous_primary_targets(architecture_decision: dict[str, Any]) -> set[str]:
    rejected = set()
    for outcome in list(architecture_decision.get("first_slice_reselection_history") or []):
        targets = list(dict(outcome or {}).get("selected_targets") or [])
        if targets:
            rejected.add(str(targets[0]))
    return rejected

def _viable_candidates(
    sources: list[str],
    context: dict[str, dict[str, Any]],
    architecture_decision: dict[str, Any],
    *,
    limit: int,
    minimum_semantic_score: int = 0,
    selection_request: dict[str, Any] | None = None,
) -> tuple[list[str], list[dict[str, Any]]]:
    first_slice = dict(architecture_decision.get("first_slice_contract") or {})
    knowledge_rule = str(first_slice.get("knowledge_rule") or "")
    ranked = []
    for index, source in enumerate(sources):
        source_context = context.get(source)
        profile = first_slice_viability(source, source_context, knowledge_rule=knowledge_rule)
        snippet = dict(dict(source_context or {}).get("snippet") or {})
        structural = dict(snippet.get("structural_contract") or {})
        decorators = {
            str(value).strip().lower().removeprefix("@").split("(", 1)[0]
            for value in list(snippet.get("decorators") or structural.get("decorators") or [])
        }
        rules = [str(row.get("rule_id") or "") for row in profile.get("matched_rules") or []]
        ranked.append({
            "source": source, "target": source, "index": index,
            "architecture_significance": (
                architecture_target_score(source) if architecture_contract_has_priority(source, structural) else 0
            ),
            "environment_ready": _environment_ready_callable(source_context),
            "receiver_independent": (
                snippet.get("target_binding") == "function_symbol"
                or bool({"staticmethod", "classmethod"} & set(snippet.get("decorators") or []))
            ),
            "property_accessor": "property" in decorators,
            **contract_quality(source, source_context, sources), **profile,
            "viability_eligible": profile["status"] == "eligible" and not profile.get("reselection_required"),
            "argument_count": len(list(dict(snippet.get("signature") or {}).get("args") or [])),
            "argument_usage_types": dict(structural.get("argument_usage_types") or {}),
            "dependency_readiness": dict(dict(source_context or {}).get("dependency_readiness") or {}),
            "ranking_reasons": [f"execution cost requires reselection: {', '.join(rules)}"] if rules else [],
            "return_paths": int(structural.get("return_paths") or 0),
            "typed_argument_count": int(structural.get("typed_argument_count") or 0),
            "state_mutation": bool(structural.get("state_mutation")),
            "observed_side_effects": list(structural.get("observed_side_effects") or []),
            "output_inference_basis": str(structural.get("output_inference_basis") or ""),
        })
    ranked.sort(key=lambda row: (
        -int(bool(row["environment_ready"])),
        int(bool(row["property_accessor"])),
        int(bool(row["state_mutation"] or row["observed_side_effects"])),
        -int(row["semantic_score"]),
        -int(row["contract_shape_score"]),
        -(int(row["score"]) + int(row["architecture_significance"])),
        -int(row["architecture_significance"]),
        -int(bool(row["receiver_independent"])),
        str(row["target"]),
        int(row["index"]),
    ))
    ranked = apply_selection_policies(ranked, dict(selection_request or {}))
    qualified = [
        row for row in ranked
        if (row["viability_eligible"] or row.get("selection_policy_ids")) and
        _semantic_threshold_satisfied(row, context.get(str(row["target"])), minimum_semantic_score)
    ]
    return [str(row["target"]) for row in qualified[:limit]], ranked

def _row_sources(value: Any) -> list[str]:
    sources = []
    for row in _rows(value):
        source = row.get("source") or row.get("target") or row.get("capability")
        if not source and row.get("path") and row.get("name"):
            source = f"{row['path']}:{row['name']}"
        if source:
            sources.append(str(source))
    return sources


def _qualify_ambiguous_method_sources(
    sources: list[str], context: dict[str, dict[str, Any]]
) -> list[str]:
    qualified: list[str] = []
    for source in sources:
        snippet = dict(dict(context.get(source) or {}).get("snippet") or {})
        if snippet.get("target_binding") != "ambiguous_method_symbol":
            qualified.append(source)
            continue
        path, _, symbol = source.partition(":")
        owners = [
            str(row.get("class_name") or "")
            for row in list(snippet.get("symbol_occurrences") or [])
            if isinstance(row, dict) and row.get("kind") == "method" and row.get("class_name")
        ]
        qualified.extend(f"{path}:{owner}.{symbol}" for owner in owners)
    return list(dict.fromkeys(qualified))


def _rows(value: Any) -> list[dict[str, Any]]:
    return [dict(row) for row in list(value or []) if isinstance(row, dict)]


def _environment_ready_callable(context: dict[str, Any] | None) -> bool:
    row = dict(context or {})
    snippet = dict(row.get("snippet") or {})
    readiness = dict(row.get("dependency_readiness") or {})
    eligibility = standalone_target_eligibility({"target_binding": snippet.get("target_binding")})
    return bool(
        _callable_source_context(row, snippet)
        and snippet.get("text")
        and readiness.get("status") == "ready"
        and eligibility.get("eligible")
    )


def _declared_dependency_callable(
    context: dict[str, Any] | None,
    declared_packages: set[str],
    policy: dict[str, Any],
) -> bool:
    if not policy.get("allow_declared_dependency_candidates", False):
        return False
    row = dict(context or {})
    snippet = dict(row.get("snippet") or {})
    readiness = dict(row.get("dependency_readiness") or {})
    missing = {str(item) for item in readiness.get("missing_external_modules") or []}
    eligibility = standalone_target_eligibility({"target_binding": snippet.get("target_binding")})
    return bool(
        missing
        and all(declared_package_satisfies_module(item, declared_packages) for item in missing)
        and _callable_source_context(row, snippet)
        and snippet.get("text")
        and eligibility.get("eligible")
    )


def _callable_source_context(row: dict[str, Any], snippet: dict[str, Any]) -> bool:
    return bool(
        row.get("node_kind") == "function"
        or snippet.get("target_binding") in {"function_symbol", "method_symbol"}
    )


def _mark_manifest_declared_context(
    selected: list[str],
    expanded_context: dict[str, dict[str, Any]],
    declared_packages: set[str],
    policy: dict[str, Any],
) -> None:
    for source in selected:
        row = dict(expanded_context.get(source) or {})
        if not _declared_dependency_callable(row, declared_packages, policy):
            continue
        readiness = dict(row.get("dependency_readiness") or {})
        readiness.update({
            "status": "manifest_declared",
            "declaration_source": "project dependency manifests",
            "executable_probe_required": True,
        })
        row["dependency_readiness"] = readiness
        expanded_context[source] = row
