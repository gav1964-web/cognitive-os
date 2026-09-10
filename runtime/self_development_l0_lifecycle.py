"""Gate, stage, quarantine, and rehearse rollback for prospective L0 lessons."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any

from .self_development_change import interpret_self_development_change
from .self_development_experiment import verify_self_development_experiment


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "self_development_l0_lifecycle.json"


class L0LifecycleError(ValueError):
    """Raised when a prospective L0 lifecycle request is unsafe."""


@lru_cache(maxsize=1)
def load_l0_lifecycle_policy(path: str | None = None) -> dict[str, Any]:
    source = Path(path) if path else POLICY_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "self_development_l0_lifecycle.v1":
        raise L0LifecycleError("L0 lifecycle policy schema mismatch")
    if payload.get("status") != "active":
        raise L0LifecycleError("L0 lifecycle policy must be active")
    if int(payload.get("minimum_independent_projects") or 0) < 3:
        raise L0LifecycleError("L0 lifecycle requires three independent projects")
    if set(payload.get("required_verification") or []) != {
        "unseen_project_holdout", "no_role_regression", "independent_evaluator",
        "baseline_candidate_experiment",
    }:
        raise L0LifecycleError("L0 lifecycle verification gates are incomplete")
    invariants = dict(payload.get("invariants") or {})
    if not all(invariants.get(key) is True for key in (
        "digest_bound_staging", "rollback_rehearsal_required"
    )):
        raise L0LifecycleError("L0 lifecycle safety gates are incomplete")
    if any(invariants.get(key) is not False for key in (
        "active_kb_write", "source_apply", "automatic_promotion"
    )):
        raise L0LifecycleError("L0 lifecycle cannot write active state")
    return payload


def evaluate_l0_candidate(
    candidate: dict[str, Any],
    *,
    verification: dict[str, Any] | None = None,
    reviewer_decision: dict[str, Any] | None = None,
    evidence_root: Path | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rules = policy or load_l0_lifecycle_policy()
    dossier = dict(candidate.get("dossier") or {})
    proposal = dict(dossier.get("proposal") or {})
    classification = dict(proposal.get("classification") or {})
    verification = dict(verification or {})
    reviewer = dict(reviewer_decision or {})
    propose_admission = interpret_self_development_change(proposal, action="propose")
    foundational = {
        "change_class_is_L0": classification.get("class") == "L0",
        "known_target_kind": classification.get("known_target_kind") is True,
        "proposal_integrity": propose_admission.get("status") == "allowed",
        "independent_project_floor": int(candidate.get("independent_project_count") or 0)
        >= int(rules["minimum_independent_projects"]),
        "target_is_role_knowledge": str(dict(proposal.get("change") or {}).get("target") or "")
        .startswith("knowledge/role_knowledge/"),
    }
    verification_checks = {
        "unseen_project_holdout": verification.get("unseen_project_holdout") is True,
        "no_role_regression": verification.get("no_role_regression") is True,
        "independent_evaluator": verification.get("independent_evaluator") is True,
        "baseline_candidate_experiment": verify_self_development_experiment(
            dict(verification.get("experiment") or {}), evidence_root=evidence_root
        ),
    }
    decision = str(reviewer.get("decision") or "")
    reviewer_checks = {
        "reviewer_artifact": reviewer.get("artifact_type") == "SelfDevelopmentL0ReviewerDecision",
        "reviewer_decision_allowed": decision in set(rules["allowed_reviewer_decisions"]),
        "reviewer_reason_present": bool(reviewer.get("reason")),
        "proposal_id_matches": reviewer.get("proposal_id") == proposal.get("proposal_id"),
    }
    if not all(foundational.values()):
        status = "blocked"
    elif not all(verification_checks.values()):
        status = "holdout_required"
    elif not all(reviewer_checks.values()):
        status = "review_required"
    elif decision == "approve_staging":
        status = "staging_ready"
    else:
        status = "quarantine_required"
    return {
        "artifact_type": "SelfDevelopmentL0CandidateAdmission",
        "status": status,
        "proposal_id": proposal.get("proposal_id"),
        "checks": {**foundational, **verification_checks, **reviewer_checks},
        "failed_checks": [
            name for name, passed in {**foundational, **verification_checks, **reviewer_checks}.items()
            if not passed
        ],
        "reviewer_decision": decision or None,
        "active_kb_write": False,
        "promotion_applied": False,
    }


def run_l0_staging_transaction(
    *,
    root: Path,
    candidate: dict[str, Any],
    verification: dict[str, Any],
    reviewer_decision: dict[str, Any],
    write: bool = False,
    rehearse_rollback: bool = True,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = root.resolve()
    rules = policy or load_l0_lifecycle_policy()
    admission = evaluate_l0_candidate(
        candidate,
        verification=verification,
        reviewer_decision=reviewer_decision,
        evidence_root=base,
        policy=rules,
    )
    dossier = dict(candidate.get("dossier") or {})
    proposal = dict(dossier.get("proposal") or {})
    proposal_id = str(proposal.get("proposal_id") or "unknown")
    quarantine = admission["status"] == "quarantine_required"
    directory_key = "quarantine_directory" if quarantine else "staging_directory"
    target = _bounded_target(base, str(rules[directory_key]), f"{proposal_id}.json")
    payload = {
        "artifact_type": "SelfDevelopmentStagedL0Candidate",
        "schema_version": "self_development_staged_l0_candidate.v1",
        "status": "quarantined" if quarantine else "staged",
        "proposal_id": proposal_id,
        "proposal_digest": _digest(proposal),
        "proposal": proposal,
        "verification": dict(verification),
        "reviewer_decision": dict(reviewer_decision),
        "active": False,
        "promotion_applied": False,
    }
    payload_digest = _digest(payload)
    before = target.read_bytes() if target.is_file() else None
    transaction = {
        "artifact_type": "SelfDevelopmentL0StagingTransaction",
        "status": admission["status"],
        "proposal_id": proposal_id,
        "admission": admission,
        "target": target.relative_to(base).as_posix(),
        "candidate_digest": payload_digest,
        "write_requested": write,
        "written": False,
        "quarantined": quarantine,
        "rollback_rehearsal": {"requested": rehearse_rollback, "status": "not_run"},
        "active_kb_write": False,
        "promotion_applied": False,
    }
    write_allowed = admission["status"] in {"staging_ready", "quarantine_required"}
    if not write or not write_allowed:
        return transaction
    _atomic_write(target, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    transaction["written"] = True
    transaction["status"] = "quarantined" if quarantine else "staged"
    if rehearse_rollback:
        _restore(target, before)
        restored = (target.read_bytes() if target.is_file() else None) == before
        transaction["rollback_rehearsal"] = {
            "requested": True,
            "status": "passed" if restored else "failed",
            "restored_pre_transaction_state": restored,
        }
        transaction["status"] = "rollback_rehearsed" if restored else "rollback_failed"
    return transaction


def _bounded_target(root: Path, directory: str, filename: str) -> Path:
    base = (root / directory).resolve()
    target = (base / filename).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise L0LifecycleError("L0 staging target escapes workspace") from exc
    return target


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _restore(path: Path, before: bytes | None) -> None:
    if before is None:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(before)
        temporary = Path(handle.name)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
