from __future__ import annotations

from typing import Any
from runtime.problem_outcome_contract import validate_problem_outcome_contract
from runtime.role_directory import load_role_directory
from runtime.spec_writer_red_team import red_team_technical_spec

def _interface_contracts_present(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    contract = dict(artifact.get("extraction_contract", {}))
    if contract.get("status") == "blocked_no_safe_candidate":
        return True, "blocked contract does not require interface contracts"
    rows = artifact.get("interface_contracts", [])
    ok = isinstance(rows, list) and bool(rows) and all(_interface_row_has_io(row) for row in rows[:6])
    return ok, "interface contracts exist"

def _defect_context_preserves_baseline_failure_evidence(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    contract = dict(artifact.get("problem_outcome_contract") or {})
    if not contract:
        return True, "not a defect-backed project context"
    valid = not validate_problem_outcome_contract(contract)
    target = str(contract.get("target") or "")
    ok = bool(
        valid
        and contract.get("status") == "evidence_bound"
        and contract.get("baseline_failures")
        and target in set(str(value) for value in contract.get("allowed_targets") or [])
    )
    return ok, "defect context binds baseline failure evidence to the selected target"

def _defect_context_preserves_causal_target_and_repair_mechanism(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    contract = dict(artifact.get("problem_outcome_contract") or {})
    if not contract:
        return True, "not a defect-backed architecture context"
    target = str(contract.get("target") or "")
    first_slice = set(str(value) for value in dict(artifact.get("first_slice_contract") or {}).get("targets") or [])
    repair = dict(contract.get("repair_design") or {})
    ok = bool(
        not validate_problem_outcome_contract(contract)
        and target in first_slice
        and (repair.get("mechanism") or repair.get("mutation_contract"))
    )
    return ok, "defect architecture preserves the causal target and repair mechanism"

def _defect_context_requires_baseline_replay_and_regression(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    contract = dict(artifact.get("problem_outcome_contract") or {})
    if not contract:
        return True, "not a defect-backed specification context"
    acceptance_ids = {
        str(row.get("id") or "") for row in artifact.get("acceptance_criteria") or []
        if isinstance(row, dict)
    }
    ok = bool(
        not validate_problem_outcome_contract(contract)
        and any(value.startswith("AC-FAILURE-REPLAY") for value in acceptance_ids)
        and "AC-FAILURE-REGRESSION" in acceptance_ids
    )
    return ok, "defect specification includes baseline replay and regression acceptance"

def _interface_row_has_io(row: object) -> bool:
    if not isinstance(row, dict):
        return False
    input_contract = row.get("input_contract")
    input_ok = bool(input_contract) or isinstance(input_contract, dict)
    return bool(row.get("source") and input_ok and row.get("output_contract"))

def _data_lifecycle_present(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    if artifact.get("data_lifecycle"):
        return True, "artifact data lifecycle exists"
    readiness = _project_answer(project_report, "6_runtime_extraction_readiness")
    return bool(readiness.get("data_lifecycle")), "ProjectMapReport data lifecycle exists"

def _error_model_present(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    rows = artifact.get("error_model", [])
    return bool(isinstance(rows, list) and rows and all(isinstance(row, dict) and row.get("handling") for row in rows[:4])), "TechnicalSpec error model exists"

def _acceptance_criteria_source_linked(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    rows = artifact.get("acceptance_criteria", [])
    ok = isinstance(rows, list) and bool(rows) and any(isinstance(row, dict) and row.get("source") for row in rows)
    return ok, "acceptance criteria include source evidence"

def _state_and_replay_policy_present(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    return bool(artifact.get("state_and_replay_policy")), "TechnicalSpec state and replay policy exists"

def _contract_shapes_specific(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    contract = dict(artifact.get("extraction_contract", {}))
    if contract.get("status") == "blocked_no_safe_candidate" or contract.get("contract_family"):
        return True, "contract is blocked or domain-shaped"
    values = list(dict(contract.get("input_contract", {})).values()) + list(dict(contract.get("output_contract", {})).values())
    ok = bool(values) and all(str(value).strip().lower() not in {"", "any", "none"} for value in values)
    return ok, "TechnicalSpec contract shapes are specific"

def _side_effect_gates_present(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    contract = dict(artifact.get("extraction_contract", {}))
    side_effects = dict(contract.get("side_effects", {}))
    declared = list(side_effects.get("declared", []) or [])
    if not declared:
        return True, "selected contract has no declared side effects"
    ok = bool(
        side_effects.get("requires_validation_gate")
        or side_effects.get("requires_process_boundary")
        or side_effects.get("idempotency_required")
        or side_effects.get("retry_policy")
    )
    return ok, "side-effecting TechnicalSpec contract has an explicit gate"

def _spec_writer_red_team_passed(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    adr = dict(artifacts.get("architecture_decision", {}))
    report = red_team_technical_spec(artifact, adr)
    return report.get("status") == "pass", f"SpecWriter red-team verdict is {report.get('handoff_verdict')}"

def _technical_spec_contract_present(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    spec = dict(artifacts.get("technical_spec", {}))
    return bool(spec.get("extraction_contract")), "technical spec extraction contract exists"

def _writable_scope_bounded(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    target = str(dict(artifact.get("implementation_target", {})).get("candidate") or "")
    writable = [str(item) for item in artifact.get("writable_scope", []) if item]
    blocked = dict(artifact.get("implementation_target", {})).get("status") == "blocked_no_safe_candidate"
    return blocked or bool(target and writable == [target]), "writable scope is exactly the target candidate"

def _verification_commands_allowlisted(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    commands = [str(item).lower() for item in artifact.get("verification_commands", [])]
    return bool(commands) and all("python" in item or "pytest" in item for item in commands), "verification commands are Python/pytest scoped"

def _plan_has_patch_intent(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    return dict(artifact.get("patch_intent", {})).get("artifact_type") == "PatchIntent", "PatchIntent is present"

def _plan_delta_propagated(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    delta = dict(artifact.get("implementation_delta") or {})
    intent_delta = dict(dict(artifact.get("patch_intent") or {}).get("implementation_delta") or {})
    return bool(delta and intent_delta == delta), "ImplementationDelta is preserved in PatchIntent"

def _executor_handoff_present(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    return bool(artifact.get("executor_handoff")), "executor handoff is present"

def _rollback_policy_present(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    return bool(dict(artifact.get("rollback_plan", {})).get("registry_policy")), "rollback registry policy is present"

def _contract_test_matrix_required(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    return bool(artifact.get("contract_test_matrix")), "contract test matrix exists"

def _negative_tests_required(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    return bool(artifact.get("negative_tests")), "negative tests exist"

def _external_calls_faked_by_default(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    strategy = dict(artifact.get("test_strategy", {}))
    text = str(strategy).lower()
    requires_external = any(marker in text for marker in ("network", "http", "api", "browser", "subprocess", "external"))
    explicit_fake = "fake" in text or bool(artifact.get("dependency_policy"))
    return (not requires_external) or explicit_fake, "external-call policy is explicit or no external boundary is in scope"

def _negative_tests_present(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    return _negative_tests_required(artifact, artifacts, project_report)

def _contract_matrix_targets_candidate(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    target = str(dict(artifact.get("test_target", {})).get("candidate") or "")
    rows = artifact.get("contract_test_matrix", [])
    return bool(target and any(isinstance(row, dict) and row.get("target") == target for row in rows)), "contract tests target selected candidate"

def _verification_is_project_scoped(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    return bool(artifact.get("smoke_checklist")), "project-scoped smoke checklist exists"

def _target_or_blocked_handoff_present(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    blocked = dict(artifact.get("boundary", {})).get("track") == "blocked_handoff"
    return bool(artifact.get("target") or blocked), "task tree has a target or controlled blocked handoff"

def _dependencies_acyclic(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    nodes = [dict(row) for row in artifact.get("nodes", []) if isinstance(row, dict)]
    dependencies = {str(row.get("id")): [str(item) for item in row.get("depends_on", [])] for row in nodes}
    resolved: set[str] = set()
    while dependencies:
        ready = [node_id for node_id, refs in dependencies.items() if all(ref in resolved for ref in refs)]
        if not ready:
            return False, "task tree contains a cycle or dangling dependency"
        for node_id in ready:
            resolved.add(node_id)
            dependencies.pop(node_id)
    return bool(nodes), "task tree dependencies are acyclic and resolvable"

def _acceptance_coverage_explicit(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    coverage = dict(artifact.get("coverage", {}))
    return isinstance(coverage.get("unmapped_acceptance_ids"), list), "acceptance coverage records unmapped obligations explicitly"

def _changes_are_dependency_ordered(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    changes = [dict(row) for row in artifact.get("nodes", []) if isinstance(row, dict) and row.get("kind") == "change"]
    return all(row.get("depends_on") for row in changes), "every change node has an explicit predecessor"

def _acceptance_is_fully_mapped(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    coverage = dict(artifact.get("coverage", {}))
    return not list(coverage.get("unmapped_acceptance_ids") or []), "all bounded acceptance obligations map to task nodes"

def _evidence_refs_present(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    nodes = [dict(row) for row in artifact.get("nodes", []) if isinstance(row, dict)]
    return bool(nodes) and all(row.get("evidence_refs") for row in nodes), "every task node points to upstream evidence"

def _stop_conditions_explicit(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    return bool(artifact.get("stop_conditions")), "task tree declares executor stop conditions"

def _scope_preserved(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    return dict(artifact.get("coverage_assessment", {})).get("scope_preserved") is True, "review confirms scope preservation"

def _contract_violations_checked(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    return isinstance(artifact.get("contract_violations"), list), "contract violations list exists"

def _promotion_requires_human_review(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    policy = dict(artifact.get("promotion_policy") or {})
    return bool(
        policy.get("automatic_promotion_forbidden") is True
        and policy.get("human_release_approval_required") is True
    ), "human release approval and automatic-promotion prohibition are represented"

def _recommendation_explicit(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    return artifact.get("recommendation") in {"approve", "approve_with_risks", "request_rework"}, "review recommendation is explicit"

def _risks_have_mitigation(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    return _risks_are_actionable(artifact, artifacts, project_report)

def _review_target_matches_plan(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    reviewed = str(dict(artifact.get("review_target", {})).get("candidate") or "")
    planned = str(dict(dict(artifacts.get("implementation_plan", {})).get("implementation_target", {})).get("candidate") or "")
    blocked = dict(artifact.get("review_target", {})).get("binding_status") == "blocked_no_safe_candidate"
    return blocked or bool(reviewed and reviewed == planned), "review target matches implementation target"

def _evidence_refs_required(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    return bool(artifact.get("evidence_refs") or artifact.get("source_cases")), "evidence refs exist"

def _source_attribution_required(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    return bool(artifact.get("teacher_reference") or artifact.get("source") or artifact.get("source_cases")), "source attribution exists"

def _kb_admission_policy_required(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    policy = dict(artifact.get("evidence_policy", {}))
    return policy.get("automatic_self_promotion_forbidden") is True or artifact.get("kb_policy", {}).get("auto_promote") is False, "KB admission forbids automatic promotion"

def _candidate_has_evidence(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    return _evidence_refs_required(artifact, artifacts, project_report)

def _facts_and_judgments_separated(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    policy = dict(artifact.get("evidence_policy", {}))
    return policy.get("facts_require_evidence") is True or policy.get("judgments_are_reviewed_separately") is True, "facts and judgments policy exists"

def _approval_gates_declared(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    policy = dict(artifact.get("evidence_policy", {}))
    return bool(policy.get("required_approvals")), "required approvals are declared"

def _unknown_check(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    return False, "unknown role gate or quality criterion"

def _project_answer(project_report: dict[str, Any], *keys: str) -> dict[str, Any]:
    answers = dict(project_report.get("answers", {}))
    for key in keys:
        value = answers.get(key)
        if isinstance(value, dict):
            return value
    return {}

