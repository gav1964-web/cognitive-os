from __future__ import annotations

from runtime.project_development_delta import development_delta_transform
from runtime.project_development_experiment import _admission
from runtime.project_failure_evidence_packet import evidence_packet_digest


def _complete_packet_checks() -> dict[str, bool]:
    return {
        "stable_failure_signature": True,
        "exact_target_is_source_backed": True,
        "failing_test_source_is_present": True,
        "observed_failure_is_detailed": True,
    }


def _complete_packet(target: str) -> dict:
    packet = {
        "artifact_type": "ProjectFailureEvidencePacket",
        "schema_version": "project_failure_evidence_packet.v1",
        "status": "complete",
        "target": target,
        "failure_signature": "stable",
        "observed_failure": "AssertionError: expected empty value, got IndexError for empty input",
        "target_source": {"path": "pkg.py", "symbol": "parse_value"},
        "test_sources": [{"path": "tests/test_pkg.py", "nodeid": "test_empty"}],
        "reproduction": {"matching_repetitions": 2, "stable_signature": True},
        "execution_authorized": False,
        "checks": _complete_packet_checks(),
    }
    packet["packet_digest"] = evidence_packet_digest(packet)
    return packet


def _decision(*, authorized: bool) -> dict:
    return {
        "selected_issue": {
            "issue_id": "ISSUE-001",
            "rule_id": "weak_contracts",
            "failure_specific_reducer_required": True,
            "affected_targets": ["pkg.py:parse_value"],
            "failure_evidence": [{
                "target": "pkg.py:parse_value",
                "authority": "failing_contract_test",
                "failure_signature": "stable",
                "failing_nodeids": ["tests/test_pkg.py::test_empty"],
            }],
            "failure_evidence_packet": _complete_packet("pkg.py:parse_value"),
            "causal_hypothesis": {
                "status": "llm_hypothesis_review_required",
                "mechanism": "Delimiter indexing occurs before the optional empty-input boundary is handled.",
                "evidence": ["failure_signature:stable"],
                "execution_authority": False,
            },
            "repair_design": {
                "status": "llm_hypothesis_review_required",
                "target": "pkg.py:parse_value",
                "mechanism": "Handle the optional empty value before delimiter extraction.",
                "mutation_contract": {
                    "precondition": "Input is empty and absence is permitted.",
                    "change": "Return the empty representation before splitting.",
                    "preserved_behavior": "Non-empty delimited values remain unchanged.",
                },
                "evidence": ["failure_signature:stable"],
            },
            "allowed_operator_ids": [],
            "llm_training_replay": {
                "authorized": authorized,
                "scope": "consumed_case_sandbox_only" if authorized else None,
            },
        },
        "selected_option": {"option_id": "ISSUE-001:contract_characterization"},
    }


def _spec() -> dict:
    return {
        "artifact_type": "TechnicalSpec",
        "source_evidence": [{
            "source": "pkg.py:parse_value",
            "signature": {
                "args": [{"name": "value", "annotation": "str"}],
                "returns": "str",
            },
        }],
    }


def test_llm_mutation_is_ready_only_for_consumed_training_replay() -> None:
    transform = development_delta_transform(_decision(authorized=True), {})

    result = transform(_spec())
    intent = result["implementation_delta"]["intent"]

    assert result["implementation_delta"]["status"] == "ready"
    assert intent["authority"] == "explicit_llm_training_replay"
    assert intent["operator_id"] is None
    assert intent["failure_evidence_packet"]["status"] == "complete"
    assert intent["causal_hypothesis"]["execution_authority"] is False


def test_llm_mutation_without_training_authorization_requires_synthesis() -> None:
    transform = development_delta_transform(_decision(authorized=False), {})

    result = transform(_spec())

    assert result["implementation_delta"]["status"] == "semantic_synthesis_required"
    assert result["implementation_delta"]["intent"]["authority"] == "none"


def test_complete_llm_training_packet_can_override_project_level_pilot_stop() -> None:
    spec = development_delta_transform(_decision(authorized=True), {})(_spec())
    plan = {
        "artifact_type": "ImplementationPlan",
        "implementation_delta": spec["implementation_delta"],
    }
    artifacts = {
        "spec": spec,
        "plan": plan,
        "tests": {"artifact_type": "TestPlan"},
        "tree": {"artifact_type": "ProgrammerTaskTree"},
    }

    result = _admission(
        {
            "status": "completed_aligned",
            "review_recommendation": "approve_with_risks",
        },
        artifacts,
        {
            "execution_policy": {
                "required_handoff_status": "completed_aligned",
                "allowed_review_recommendations": ["approve_with_risks"],
                "apply_source": False,
            }
        },
        {"pilot_route": {"status": "analysis_only_stop"}},
    )

    assert result["status"] == "admitted"
    assert result["bounded_training_replay_override"] is True


def test_known_operator_training_packet_can_override_project_pilot_stop() -> None:
    target = "pkg.py:parse_value"
    operator = "guard_empty_input"
    spec = {
        "artifact_type": "TechnicalSpec",
        "extraction_contract": {"allowed_operator_ids": [operator]},
    }
    plan = {
        "artifact_type": "ImplementationPlan",
        "implementation_delta": {
            "status": "ready",
            "intent": {
                "authority": "explicit_training_replay",
                "target_symbol": target,
                "operator_id": operator,
                "allowed_operator_ids": [operator],
                "failure_evidence_packet": _complete_packet(target),
            },
        },
    }
    artifacts = {
        "spec": spec,
        "plan": plan,
        "tests": {"artifact_type": "TestPlan"},
        "tree": {"artifact_type": "ProgrammerTaskTree"},
    }

    result = _admission(
        {"status": "completed_aligned", "review_recommendation": "approve_with_risks"},
        artifacts,
        {
            "execution_policy": {
                "required_handoff_status": "completed_aligned",
                "allowed_review_recommendations": ["approve_with_risks"],
                "apply_source": False,
            }
        },
        {"pilot_route": {"status": "analysis_only_stop"}},
    )

    assert result["status"] == "admitted"
    assert result["bounded_training_replay_override"] is True


def test_training_override_rejects_operator_allowlist_mismatch() -> None:
    target = "pkg.py:parse_value"
    artifacts = {
        "spec": {
            "artifact_type": "TechnicalSpec",
            "extraction_contract": {"allowed_operator_ids": ["different_operator"]},
        },
        "plan": {
            "artifact_type": "ImplementationPlan",
            "implementation_delta": {
                "status": "ready",
                "intent": {
                    "authority": "explicit_training_replay",
                    "target_symbol": target,
                    "operator_id": "guard_empty_input",
                    "allowed_operator_ids": ["guard_empty_input"],
                    "failure_evidence_packet": _complete_packet(target),
                },
            },
        },
        "tests": {"artifact_type": "TestPlan"},
        "tree": {"artifact_type": "ProgrammerTaskTree"},
    }

    result = _admission(
        {"status": "completed_aligned", "review_recommendation": "approve_with_risks"},
        artifacts,
        {
            "execution_policy": {
                "required_handoff_status": "completed_aligned",
                "allowed_review_recommendations": ["approve_with_risks"],
                "apply_source": False,
            }
        },
        {"pilot_route": {"status": "analysis_only_stop"}},
    )

    assert result["status"] == "blocked"
    assert result["bounded_training_replay_override"] is False


def test_training_override_rejects_incomplete_evidence_check_set() -> None:
    decision = _decision(authorized=True)
    decision["selected_issue"]["failure_evidence_packet"]["checks"].pop(
        "observed_failure_is_detailed"
    )
    decision["selected_issue"]["failure_evidence_packet"]["packet_digest"] = (
        evidence_packet_digest(decision["selected_issue"]["failure_evidence_packet"])
    )
    spec = development_delta_transform(decision, {})(_spec())
    artifacts = {
        "spec": spec,
        "plan": {
            "artifact_type": "ImplementationPlan",
            "implementation_delta": spec["implementation_delta"],
        },
        "tests": {"artifact_type": "TestPlan"},
        "tree": {"artifact_type": "ProgrammerTaskTree"},
    }

    result = _admission(
        {"status": "completed_aligned", "review_recommendation": "approve_with_risks"},
        artifacts,
        {
            "execution_policy": {
                "required_handoff_status": "completed_aligned",
                "allowed_review_recommendations": ["approve_with_risks"],
                "apply_source": False,
            }
        },
        {"pilot_route": {"status": "analysis_only_stop"}},
    )

    assert result["status"] == "blocked"
    assert result["bounded_training_replay_override"] is False


def test_training_override_rejects_evidence_digest_drift() -> None:
    decision = _decision(authorized=True)
    decision["selected_issue"]["failure_evidence_packet"]["observed_failure"] += " drift"
    spec = development_delta_transform(decision, {})(_spec())
    artifacts = {
        "spec": spec,
        "plan": {
            "artifact_type": "ImplementationPlan",
            "implementation_delta": spec["implementation_delta"],
        },
        "tests": {"artifact_type": "TestPlan"},
        "tree": {"artifact_type": "ProgrammerTaskTree"},
    }

    result = _admission(
        {"status": "completed_aligned", "review_recommendation": "approve_with_risks"},
        artifacts,
        {
            "execution_policy": {
                "required_handoff_status": "completed_aligned",
                "allowed_review_recommendations": ["approve_with_risks"],
                "apply_source": False,
            }
        },
        {"pilot_route": {"status": "analysis_only_stop"}},
    )

    assert result["status"] == "blocked"
    assert result["bounded_training_replay_override"] is False
