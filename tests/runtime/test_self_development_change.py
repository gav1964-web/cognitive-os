from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from runtime.self_development_change import (
    SelfDevelopmentChangeError,
    build_capability_change_dossier,
    build_self_development_change_proposal,
    build_shadow_change_dossier,
    classify_self_development_change,
    interpret_self_development_change,
    load_self_development_change_policy,
)
from runtime.evidence_ledger import promote_evidence


ROOT = Path(__file__).resolve().parents[2]


def _proposal(
    target_kind: str = "kb_entry",
    *,
    patch_digest: str | None = "abc123",
    impact: dict | None = None,
    verification: dict | None = None,
) -> dict:
    return build_self_development_change_proposal(
        problem={"summary": "Repeated wrong selection", "failure_signature": "selection:v1"},
        hypothesis={"summary": "A bounded rule fixes it", "expected_effect": "fewer false selections"},
        change={
            "target": "knowledge/role_knowledge/example.json",
            "target_kind": target_kind,
            "operation": "append_verified_pattern",
            "patch_digest": patch_digest,
        },
        evidence=[{"artifact_type": "FieldEvidence", "report": "report.json"}],
        impact_map=impact or {
            "components": ["knowledge_admission"],
            "roles": ["architect"],
            "project_types": ["library_pure_transform"],
            "contracts": [],
        },
        verification=verification or {
            "regression_passed": True,
            "independent_holdout_passed": True,
            "independent_evaluator": True,
            "evaluator_fingerprint": "eval-v1",
            "generated_stub_gate_passed": True,
        },
        rollback_plan={"strategy": "restore promotion snapshot"},
    )


def _verified_receipts(root: Path) -> dict:
    source = root / "artifacts" / "independent-verification.json"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(json.dumps({
        "artifact_type": "IndependentSelfDevelopmentVerification",
        "status": "passed",
        "checks": {
            "regression": True,
            "independent_holdout": True,
            "generated_stub_gate": True,
        },
        "holdout_provenance": {
            "selection_digest": "sha256:" + "a" * 64,
            "case_count": 5,
            "source_lineages": 3,
        },
        "generated_stub_count": 0,
    }), encoding="utf-8")
    entry = promote_evidence(
        root=root,
        source=source,
        producer_fingerprint="self-development-runner:v1",
        evaluator_fingerprint="independent-evaluator:v2",
        replay_command=["python", "tools/self_development_trial.py", "--frozen"],
    )
    path = entry["ledger_path"]
    return {
        "evaluator_fingerprint": "independent-evaluator:v2",
        "receipts": {gate: path for gate in (
            "regression", "independent_holdout", "independent_evaluator",
            "evaluator_fingerprint", "generated_stub_gate",
        )},
    }


def test_policy_loads_complete_l0_l4_authority_matrix() -> None:
    policy = load_self_development_change_policy(
        str(ROOT / "config" / "self_development_change_policy.json")
    )

    assert set(policy["classes"]) == {"L0", "L1", "L2", "L3", "L4"}
    assert policy["classes"]["L3"]["authority"]["promote"] == "external_architect"
    assert policy["invariants"]["runtime_patch_auto_promotion"] is False


@pytest.mark.parametrize(("target_kind", "expected"), [
    ("lesson", "L0"),
    ("weight", "L1"),
    ("artifact_schema", "L2"),
    ("runtime_component", "L3"),
    ("execution_model", "L4"),
])
def test_classifier_maps_declared_target_kinds(target_kind: str, expected: str) -> None:
    result = classify_self_development_change(
        {"target_kind": target_kind}, {"changes_evaluator_architecture": False}
    )

    assert result["class"] == expected
    assert result["known_target_kind"] is True


def test_unknown_target_kind_fails_closed_to_l4() -> None:
    result = classify_self_development_change(
        {"target_kind": "surprising_new_layer"}, {}
    )

    assert result == {
        "class": "L4",
        "variant": "L4",
        "known_target_kind": False,
        "target_kind": "surprising_new_layer",
        "basis": "unknown_target_kind_defaulted_to_L4",
        "classification_review_required": True,
    }


def test_evaluator_architecture_impact_overrides_shallow_declared_kind() -> None:
    result = classify_self_development_change(
        {"target_kind": "kb_entry"}, {"changes_evaluator_architecture": True}
    )

    assert result["class"] == "L4"
    assert result["known_target_kind"] is False
    assert result["basis"] == "evaluator_architecture_impact"


def test_sensitive_l1_cannot_self_promote(tmp_path: Path) -> None:
    proposal = _proposal(
        "promotion_threshold",
        impact={
            "components": ["promotion"],
            "roles": ["reviewer"],
            "project_types": ["library_pure_transform"],
            "contracts": [],
            "changes_admission_or_promotion": True,
        },
        verification=_verified_receipts(tmp_path),
    )

    denied = interpret_self_development_change(
        proposal, action="promote", authority="promotion_controller"
    )
    allowed = interpret_self_development_change(
        proposal, action="promote", authority="external_architect", evidence_root=tmp_path
    )

    assert proposal["classification"]["variant"] == "L1-sensitive"
    assert denied["status"] == "blocked"
    assert denied["required_authority"] == "external_architect"
    assert allowed["status"] == "allowed"
    assert allowed["execution_authorized"] is False


def test_runtime_change_can_be_proposed_but_requires_external_promotion(tmp_path: Path) -> None:
    proposal = _proposal("runtime_component", verification=_verified_receipts(tmp_path))

    assert interpret_self_development_change(proposal, action="propose")["status"] == "allowed"
    pending = interpret_self_development_change(proposal, action="promote")
    approved = interpret_self_development_change(
        proposal, action="promote", authority="external_architect", evidence_root=tmp_path
    )

    assert pending["status"] == "external_review_required"
    assert approved["status"] == "allowed"
    assert approved["promotion_applied"] is False


def test_missing_runtime_gates_block_even_with_external_authority() -> None:
    proposal = _proposal(
        "runtime_component",
        patch_digest=None,
        verification={
            "regression_passed": False,
            "independent_holdout_passed": False,
            "independent_evaluator": False,
            "evaluator_fingerprint": "",
            "generated_stub_gate_passed": False,
        },
    )

    admission = interpret_self_development_change(
        proposal, action="promote", authority="external_architect"
    )

    assert admission["status"] == "blocked"
    assert set(admission["blocking_reasons"]) == {
        "regression", "independent_holdout", "independent_evaluator",
        "evaluator_fingerprint", "generated_stub_gate",
    }


def test_self_reported_verification_booleans_do_not_pass_evidence_gates() -> None:
    admission = interpret_self_development_change(
        _proposal("runtime_component"),
        action="promote",
        authority="external_architect",
    )

    assert admission["status"] == "blocked"
    assert {"regression", "independent_holdout", "independent_evaluator"}.issubset(
        admission["blocking_reasons"]
    )


def test_proposal_digest_detects_post_build_mutation() -> None:
    proposal = _proposal()
    tampered = copy.deepcopy(proposal)
    tampered["change"]["target"] = "knowledge/role_knowledge/other.json"

    admission = interpret_self_development_change(tampered, action="propose")

    assert admission["status"] == "blocked"
    assert "proposal_digest_mismatch" in admission["blocking_reasons"]


def test_unknown_kind_dossier_stays_shadow_and_requires_classification_review() -> None:
    dossier = build_shadow_change_dossier(_proposal("unknown_layer"))

    assert dossier["status"] == "shadow_only"
    assert dossier["admissions"]["propose"]["status"] == "allowed"
    assert dossier["admissions"]["sandbox"]["status"] == "external_review_required"
    assert "classification_review" in dossier["admissions"]["sandbox"]["required_gates"]
    assert dossier["constraints"]["apply_source"] is False


def test_capability_request_becomes_l3_shadow_dossier() -> None:
    dossier = build_capability_change_dossier({
        "request_id": "cdr_123",
        "gap_id": "gap:selection",
        "label": "Selection plugin is missing",
        "observed_projects": ["one", "two", "three"],
        "role_scope": ["architect", "spec_writer"],
        "missing_capability": "candidate_selection_discriminator",
    }, evaluator_fingerprint="engine-v1")

    proposal = dossier["proposal"]
    assert proposal["classification"]["class"] == "L3"
    assert len(proposal["evidence"]) == 3
    assert dossier["admissions"]["promote"]["status"] == "external_review_required"
    assert dossier["constraints"]["promotion_applied"] is False


def test_policy_rejects_overlapping_target_kinds(tmp_path: Path) -> None:
    payload = json.loads(
        (ROOT / "config" / "self_development_change_policy.json").read_text(encoding="utf-8")
    )
    payload["classes"]["L4"]["target_kinds"].append("kb_entry")
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(SelfDevelopmentChangeError, match="multiple classes"):
        load_self_development_change_policy(str(path))
