"""Bounded implementation-delta transforms for project development."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .source_contract_semantics import infer_source_contract


def development_delta_transform(decision: dict[str, Any], policy: dict[str, Any]):
    issue = dict(decision.get("selected_issue") or {})
    option = dict(decision.get("selected_option") or {})
    reducers = (
        list(issue.get("allowed_operator_ids") or [])
        if issue.get("failure_specific_reducer_required") is True
        else list(dict(policy.get("verified_issue_reducers") or {}).get(str(issue.get("rule_id") or "")) or [])
    )

    def transform(artifact: dict[str, Any]) -> dict[str, Any]:
        if (
            artifact.get("artifact_type") == "TechnicalSpec"
            and issue.get("failure_specific_reducer_required") is True
        ):
            return _bind_failure_repair_contract(artifact, issue, reducers)
        if artifact.get("artifact_type") != "ImplementationPlan" or not reducers:
            return artifact
        row = deepcopy(artifact)
        delta = dict(row.get("implementation_delta") or {})
        if delta.get("status") != "semantic_synthesis_required":
            return artifact
        delta.update({
            "status": "ready",
            "intent": {
                "kind": "apply_verified_project_development_reducer",
                "statement": f"Select exactly one verified reducer for {issue.get('rule_id')} inside the selected target.",
                "operator_id": reducers[0],
                "allowed_operator_ids": reducers,
            },
            "reason": "ProjectDevelopmentDecision selected an allowlisted deterministic issue reducer.",
            "evidence": [
                {"source": "ProjectDevelopmentDecision", "value": option.get("option_id")},
                {"source": "project_development_policy.verified_issue_reducers", "value": reducers},
            ],
        })
        row["implementation_delta"] = delta
        patch_intent = dict(row.get("patch_intent") or {})
        patch_intent["status"] = "ready"
        patch_intent["implementation_delta"] = delta
        row["patch_intent"] = patch_intent
        return row

    return transform


def _bind_failure_repair_contract(
    artifact: dict[str, Any], issue: dict[str, Any], reducers: list[str]
) -> dict[str, Any]:
    targets = [str(value) for value in issue.get("affected_targets") or [] if value]
    failure_evidence = [dict(value) for value in issue.get("failure_evidence") or [] if isinstance(value, dict)]
    if len(targets) != 1 or not failure_evidence:
        return artifact
    target = targets[0]
    matching = next(
        (dict(row) for row in artifact.get("source_evidence") or [] if str(row.get("source") or "") == target),
        {},
    )
    structural = infer_source_contract(matching) if matching else {}
    inputs, outputs = _repair_io_contract(matching, structural)
    nodeids = list(dict(failure_evidence[0]).get("failing_nodeids") or [])
    observed_side_effects = list(structural.get("observed_side_effects") or [])
    contract = {
        "status": "failure_repair_ready",
        "mode": "failure_repair",
        "candidate": target,
        "candidate_score": 100,
        "selection_reason": "Repeated project-native failing test authorizes repair of the unique production target.",
        "ranked_candidates": [{
            "source": target,
            "kind": "failure_backed_repair_target",
            "score": 100,
            "reasons": ["ProjectDevelopmentDecision failing_contract_test authority"],
            "side_effects": observed_side_effects,
        }],
        "input_contract": inputs,
        "output_contract": outputs,
        "side_effects": {
            "declared": observed_side_effects,
            "requires_validation_gate": bool(observed_side_effects),
            "requires_process_boundary": False,
        },
        "evidence_source": target,
        "structural_evidence": structural,
        "failure_kinds": list(issue.get("failure_kinds") or []),
        "failure_evidence": failure_evidence,
        "allowed_operator_ids": list(reducers),
        "validation_gates": [
            *([{"kind": "project_native_failure_replay", "nodeid": nodeid} for nodeid in nodeids]),
            {"kind": "source_digest_unchanged_outside_patch_scope", "target": target},
        ],
        "semantic_quality": {
            "status": "approved_with_constraints",
            "authority": "repeated_project_native_failure",
            "reasons": ["repair scope is bounded to the unique repeated production failure target"],
        },
    }
    row = deepcopy(artifact)
    row["extraction_contract"] = contract
    row["contract_mode"] = "failure_repair"
    row["first_slice_reselection_request"] = {
        "status": "not_required",
        "trigger": None,
        "current_target": target,
        "reason": "failure repair target is authority-bound and must not be reranked as an extraction candidate",
    }
    row["implementation_delta"] = {
        "status": "semantic_synthesis_required",
        "intent": {"kind": "repair_verified_project_failure", "target_symbol": target},
        "reason": "A verified failure reducer must be selected by ProjectDevelopmentDecision.",
        "evidence": failure_evidence,
    }
    row["implementation_handoff"] = {
        **dict(row.get("implementation_handoff") or {}),
        "mode": "semantic_synthesis_required",
        "patch_scope": [target],
    }
    replay_criteria = [
        {
            "id": f"AC-FAILURE-REPLAY-{index:03d}",
            "criterion": f"The original project-native failing test passes: {nodeid}",
            "verification": f"pytest {nodeid}",
            "source": target,
            "authority": "failing_contract_test",
            "requirement_id": "REQ-FAILURE-REPLAY",
        }
        for index, nodeid in enumerate(nodeids, start=1)
    ]
    failure_kinds = ", ".join(str(value) for value in issue.get("failure_kinds") or [])
    criteria = [
        *replay_criteria,
        {
            "id": "AC-FAILURE-BOUNDARY",
            "criterion": (
                f"The repaired `{target}` handles the verified failure boundary "
                f"without introducing an unapproved fallback: {failure_kinds or 'project-native failure'}"
            ),
            "verification": "targeted negative test for the recorded failing input and failure kind",
            "source": target,
            "authority": "failing_contract_test",
            "requirement_id": "REQ-FAILURE-REPAIR",
        },
        {
            "id": "AC-FAILURE-REGRESSION",
            "criterion": (
                f"The complete project-native regression suite passes and the patch remains bounded to `{target}`."
            ),
            "verification": "project-native regression command plus source digest and patch-scope checks",
            "source": target,
            "authority": "project_native_regression",
            "requirement_id": "REQ-FAILURE-REGRESSION",
        },
    ]
    row["requirements"] = [
        {
            "id": "REQ-FAILURE-REPLAY",
            "statement": f"Reproduce the recorded project-native failure for `{target}` before applying a repair.",
            "source": target,
            "target": target,
            "priority": "MUST",
        },
        {
            "id": "REQ-FAILURE-REPAIR",
            "statement": f"Apply exactly one approved failure reducer inside `{target}` and preserve its declared contract.",
            "source": "ProjectDevelopmentDecision.allowed_operator_ids",
            "target": target,
            "priority": "MUST",
        },
        {
            "id": "REQ-FAILURE-REGRESSION",
            "statement": f"Verify `{target}` with targeted replay, the complete native suite, and patch-scope invariants.",
            "source": "ProjectDevelopmentOutcomeContract.required_checks",
            "target": target,
            "priority": "MUST",
        },
    ]
    row["acceptance_criteria"] = criteria
    row["traceability_table"] = [
        {
            "requirement_id": criterion["requirement_id"],
            "requirement": next(
                requirement["statement"] for requirement in row["requirements"]
                if requirement["id"] == criterion["requirement_id"]
            ),
            "source": criterion["source"],
            "acceptance_id": criterion["id"],
            "target": target,
        }
        for criterion in criteria
    ]
    row["verification_strategy"] = {
        "targeted_replay": [
            {"target": target, "nodeid": nodeid, "assertion": "recorded failure no longer reproduces"}
            for nodeid in nodeids
        ],
        "negative_tests": [{
            "target": target,
            "failure_kind": value,
            "assertion": "the recorded failure boundary has explicit controlled behavior",
        } for value in issue.get("failure_kinds") or []],
        "regression_checks": [{
            "target": target,
            "assertion": "complete project-native suite passes and source changes remain patch-scoped",
        }],
    }
    return row


def _repair_io_contract(
    evidence: dict[str, Any], structural: dict[str, Any]
) -> tuple[dict[str, str], dict[str, str]]:
    signature = dict(evidence.get("signature") or {})
    documented = dict(structural.get("docstring_argument_types") or {})
    usage = dict(structural.get("argument_usage_types") or {})
    constraints = dict(structural.get("argument_constraint_types") or {})
    inputs = {
        str(arg.get("name")): str(
            arg.get("annotation")
            or documented.get(str(arg.get("name")))
            or usage.get(str(arg.get("name")))
            or constraints.get(str(arg.get("name")))
            or "Any"
        )
        for arg in signature.get("args") or []
        if isinstance(arg, dict) and str(arg.get("name") or "") not in {"self", "cls", ""}
    }
    output = str(signature.get("returns") or structural.get("inferred_output_type") or "Any")
    return inputs or {"input": "Any"}, {"result": output}
