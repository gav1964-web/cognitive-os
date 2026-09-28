"""Compare independently evaluated baseline and candidate experiment arms."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .evidence_ledger import promote_evidence, verify_evidence_entry
from .self_development_experiment import evaluate_self_development_experiment


def run_baseline_candidate_experiment(
    *,
    root: Path,
    queue: dict[str, Any],
    candidate_digest: str,
    baseline_receipt: str,
    candidate_receipt: str,
    write: bool = False,
) -> dict[str, Any]:
    ready = next(
        (dict(row) for row in queue.get("ready") or [] if row.get("candidate_digest") == candidate_digest),
        None,
    )
    baseline_verification = verify_evidence_entry(root=root, ledger_path=Path(baseline_receipt))
    candidate_verification = verify_evidence_entry(root=root, ledger_path=Path(candidate_receipt))
    baseline = dict(baseline_verification.get("evidence_payload") or {})
    candidate = dict(candidate_verification.get("evidence_payload") or {})
    checks = {
        "queue_candidate_ready": ready is not None and queue.get("status") == "ready_for_experiment",
        "baseline_receipt_verified": baseline_verification.get("status") == "verified",
        "candidate_receipt_verified": candidate_verification.get("status") == "verified",
        "arm_contracts_valid": _valid_arm(baseline, "baseline") and _valid_arm(candidate, "candidate"),
        "candidate_digest_bound": candidate.get("candidate_digest") == candidate_digest,
        "same_frozen_holdout": bool(baseline.get("holdout_digest"))
        and baseline.get("holdout_digest") == candidate.get("holdout_digest"),
        "same_evaluation_protocol": bool(baseline.get("evaluation_protocol_digest"))
        and baseline.get("evaluation_protocol_digest") == candidate.get("evaluation_protocol_digest"),
        "independent_evaluator": _same_independent_evaluator(
            baseline_verification, candidate_verification
        ),
        "source_snapshots_unchanged": (
            baseline.get("source_snapshot_before") == baseline.get("source_snapshot_after")
            and candidate.get("source_snapshot_before") == candidate.get("source_snapshot_after")
        ),
        "candidate_used_isolated_overlay": candidate.get("isolated_overlay") is True,
        "generated_stub_gate": int(candidate.get("generated_stub_count") or 0) == 0,
    }
    failed = [name for name, passed in checks.items() if not passed]
    base = {
        "artifact_type": "SelfDevelopmentExperimentExecution",
        "schema_version": "self_development_experiment_execution.v1",
        "status": "blocked" if failed else "comparison_ready",
        "candidate_digest": candidate_digest,
        "queue_digest": queue.get("queue_digest"),
        "baseline_receipt": baseline_receipt,
        "candidate_receipt": candidate_receipt,
        "checks": checks,
        "failed_checks": failed,
        "comparison_evidence_receipt": None,
        "experiment": {"status": "not_run"},
        "safety": {"source_apply": False, "active_kb_write": False, "promotion_applied": False},
    }
    if failed or not write:
        return {**base, "execution_digest": _digest(base)}
    evidence = _comparison_evidence(
        ready=ready or {}, baseline=baseline, candidate=candidate, checks=checks
    )
    source = _write_evidence(root, evidence)
    evaluator = str(dict(baseline_verification.get("entry") or {}).get("evaluator_fingerprint"))
    receipt = promote_evidence(
        root=root,
        source=source,
        producer_fingerprint="self_development_experiment_runner:v1",
        evaluator_fingerprint=evaluator,
        replay_command=["python", "tools/self_development_experiment_runner.py"],
    )
    experiment = evaluate_self_development_experiment(
        change_class=str((ready or {}).get("change_class")),
        target_metric=str((ready or {}).get("target_metric")),
        baseline=dict(baseline["metrics"]),
        candidate=dict(candidate["metrics"]),
        generated_stub_count=int(candidate.get("generated_stub_count") or 0),
        evidence_root=root,
        evaluation_receipt=str(receipt["ledger_path"]),
    )
    completed = {
        **base,
        "status": "completed",
        "comparison_evidence_receipt": receipt["ledger_path"],
        "experiment": experiment,
    }
    return {**completed, "execution_digest": _digest(completed)}


def _valid_arm(payload: dict[str, Any], arm: str) -> bool:
    return (
        payload.get("artifact_type") == "SelfDevelopmentExperimentArmEvidence"
        and payload.get("schema_version") == "self_development_experiment_arm.v1"
        and payload.get("status") == "passed"
        and payload.get("arm") == arm
        and isinstance(payload.get("metrics"), dict)
        and bool(payload.get("metrics"))
        and all(isinstance(value, (int, float)) for value in payload.get("metrics", {}).values())
        and payload.get("source_apply") is False
        and payload.get("promotion_applied") is False
    )


def _same_independent_evaluator(baseline: dict[str, Any], candidate: dict[str, Any]) -> bool:
    baseline_entry = dict(baseline.get("entry") or {})
    candidate_entry = dict(candidate.get("entry") or {})
    evaluator = str(baseline_entry.get("evaluator_fingerprint") or "")
    return (
        bool(evaluator)
        and evaluator == candidate_entry.get("evaluator_fingerprint")
        and evaluator != baseline_entry.get("producer_fingerprint")
        and evaluator != candidate_entry.get("producer_fingerprint")
    )


def _comparison_evidence(
    *, ready: dict[str, Any], baseline: dict[str, Any], candidate: dict[str, Any], checks: dict[str, bool]
) -> dict[str, Any]:
    return {
        "artifact_type": "SelfDevelopmentExperimentEvidence",
        "schema_version": "self_development_experiment_evidence.v1",
        "status": "passed",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidate_digest": ready.get("candidate_digest"),
        "target_metric": ready.get("target_metric"),
        "holdout_digest": baseline.get("holdout_digest"),
        "baseline_metrics": baseline.get("metrics"),
        "candidate_metrics": candidate.get("metrics"),
        "generated_stub_count": int(candidate.get("generated_stub_count") or 0),
        "checks": {
            "independent_holdout": checks["same_frozen_holdout"],
            "independent_evaluator": checks["independent_evaluator"],
            "no_role_regression": _no_regression(baseline["metrics"], candidate["metrics"]),
            "generated_stub_gate": checks["generated_stub_gate"],
            "source_snapshots_unchanged": checks["source_snapshots_unchanged"],
            "isolated_overlay": checks["candidate_used_isolated_overlay"],
        },
    }


def _no_regression(baseline: dict[str, float], candidate: dict[str, float]) -> bool:
    return set(baseline) == set(candidate) and all(candidate[key] >= value for key, value in baseline.items())


def _write_evidence(root: Path, evidence: dict[str, Any]) -> Path:
    directory = root / "artifacts" / "self_development"
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = directory / f"self_development_experiment_evidence_{stamp}.json"
    path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
