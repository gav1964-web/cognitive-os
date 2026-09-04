from __future__ import annotations

import json
from pathlib import Path

from runtime.self_development_change import (
    build_self_development_change_proposal,
    build_shadow_change_dossier,
)
from runtime.self_development_l0_lifecycle import (
    evaluate_l0_candidate,
    load_l0_lifecycle_policy,
    run_l0_staging_transaction,
)


ROOT = Path(__file__).resolve().parents[2]


def _candidate() -> dict:
    proposal = build_self_development_change_proposal(
        problem={"summary": "Repeated recognition gap", "failure_signature": "recognition:v1"},
        hypothesis={"summary": "A lesson improves recognition", "expected_effect": "fewer gaps"},
        change={
            "target": "knowledge/role_knowledge/self_development_lessons.json",
            "target_kind": "lesson",
            "operation": "append_prospective_systematic_error_lesson",
            "patch_digest": None,
        },
        evidence=[
            {"artifact_type": "ProspectiveSystematicErrorEvidence", "project": name}
            for name in ("alpha", "beta", "gamma")
        ],
        impact_map={
            "components": ["project_recognition"],
            "roles": ["project_analyzer", "researcher", "architect"],
            "project_types": ["library_pure_transform"],
            "contracts": ["classification:ambiguous_project_identity"],
        },
        verification={
            "regression_passed": False,
            "independent_holdout_passed": False,
            "independent_evaluator": False,
            "evaluator_fingerprint": "matrix-v1",
        },
        rollback_plan={"strategy": "discard staged lesson candidate"},
    )
    return {
        "independent_project_count": 3,
        "dossier": build_shadow_change_dossier(proposal),
    }


def _verification() -> dict:
    return {
        "unseen_project_holdout": True,
        "no_role_regression": True,
        "independent_evaluator": True,
    }


def _review(candidate: dict, decision: str = "approve_staging") -> dict:
    proposal_id = candidate["dossier"]["proposal"]["proposal_id"]
    return {
        "artifact_type": "SelfDevelopmentL0ReviewerDecision",
        "proposal_id": proposal_id,
        "decision": decision,
        "reason": "Evidence and scope are sufficient" if decision == "approve_staging" else "Holdout failed",
    }


def test_new_l0_candidate_requires_unseen_holdout_before_review() -> None:
    admission = evaluate_l0_candidate(_candidate())

    assert admission["status"] == "holdout_required"
    assert admission["checks"]["change_class_is_L0"] is True
    assert admission["checks"]["unseen_project_holdout"] is False
    assert admission["promotion_applied"] is False


def test_verified_candidate_requires_digest_bound_reviewer_decision() -> None:
    candidate = _candidate()
    admission = evaluate_l0_candidate(candidate, verification=_verification())

    assert admission["status"] == "review_required"
    assert admission["checks"]["reviewer_artifact"] is False


def test_staging_transaction_rehearses_real_rollback(tmp_path: Path) -> None:
    candidate = _candidate()
    transaction = run_l0_staging_transaction(
        root=tmp_path,
        candidate=candidate,
        verification=_verification(),
        reviewer_decision=_review(candidate),
        write=True,
        rehearse_rollback=True,
    )

    assert transaction["status"] == "rollback_rehearsed"
    assert transaction["written"] is True
    assert transaction["rollback_rehearsal"]["status"] == "passed"
    assert not (tmp_path / transaction["target"]).exists()
    assert transaction["active_kb_write"] is False


def test_rejected_candidate_is_quarantined_outside_active_kb(tmp_path: Path) -> None:
    candidate = _candidate()
    transaction = run_l0_staging_transaction(
        root=tmp_path,
        candidate=candidate,
        verification=_verification(),
        reviewer_decision=_review(candidate, "quarantine"),
        write=True,
        rehearse_rollback=False,
    )

    assert transaction["status"] == "quarantined"
    payload = json.loads((tmp_path / transaction["target"]).read_text(encoding="utf-8"))
    assert payload["status"] == "quarantined"
    assert payload["active"] is False
    assert transaction["promotion_applied"] is False


def test_current_l0_policy_forbids_active_kb_write() -> None:
    policy = load_l0_lifecycle_policy(
        str(ROOT / "config" / "self_development_l0_lifecycle.json")
    )

    assert policy["invariants"]["active_kb_write"] is False
    assert policy["invariants"]["automatic_promotion"] is False
