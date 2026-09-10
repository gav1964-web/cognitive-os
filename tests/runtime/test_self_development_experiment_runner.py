from __future__ import annotations

import json
from pathlib import Path

from runtime.evidence_ledger import promote_evidence
from runtime.self_development_experiment_runner import run_baseline_candidate_experiment


DIGEST = "sha256:" + "a" * 64


def _arm(root: Path, arm: str, metrics: dict[str, float], **overrides) -> str:
    payload = {
        "artifact_type": "SelfDevelopmentExperimentArmEvidence",
        "schema_version": "self_development_experiment_arm.v1",
        "status": "passed",
        "arm": arm,
        "candidate_digest": DIGEST if arm == "candidate" else None,
        "holdout_digest": "sha256:" + "b" * 64,
        "evaluation_protocol_digest": "sha256:" + "c" * 64,
        "metrics": metrics,
        "source_snapshot_before": "sha256:" + "d" * 64,
        "source_snapshot_after": "sha256:" + "d" * 64,
        "isolated_overlay": arm == "candidate",
        "generated_stub_count": 0,
        "source_apply": False,
        "promotion_applied": False,
    }
    payload.update(overrides)
    source = root / f"{arm}.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    receipt = promote_evidence(
        root=root,
        source=source,
        producer_fingerprint=f"{arm}-runner:v1",
        evaluator_fingerprint="independent-arm-evaluator:v1",
        replay_command=["pytest"],
    )
    return str(receipt["ledger_path"])


def _queue() -> dict:
    return {
        "status": "ready_for_experiment",
        "queue_digest": "sha256:" + "e" * 64,
        "ready": [{
            "candidate_digest": DIGEST,
            "change_class": "L0",
            "target_metric": "recognition_accuracy",
        }],
    }


def test_runner_completes_a_bound_improving_comparison(tmp_path: Path) -> None:
    baseline = _arm(tmp_path, "baseline", {"recognition_accuracy": 0.8, "role_continuity": 1.0})
    candidate = _arm(tmp_path, "candidate", {"recognition_accuracy": 0.82, "role_continuity": 1.0})

    result = run_baseline_candidate_experiment(
        root=tmp_path,
        queue=_queue(),
        candidate_digest=DIGEST,
        baseline_receipt=baseline,
        candidate_receipt=candidate,
        write=True,
    )

    assert result["status"] == "completed"
    assert result["experiment"]["status"] == "staging_eligible"
    assert result["comparison_evidence_receipt"]


def test_runner_rejects_holdout_drift_before_comparison(tmp_path: Path) -> None:
    baseline = _arm(tmp_path, "baseline", {"recognition_accuracy": 0.8})
    candidate = _arm(
        tmp_path, "candidate", {"recognition_accuracy": 0.9},
        holdout_digest="sha256:" + "f" * 64,
    )

    result = run_baseline_candidate_experiment(
        root=tmp_path, queue=_queue(), candidate_digest=DIGEST,
        baseline_receipt=baseline, candidate_receipt=candidate,
    )

    assert result["status"] == "blocked"
    assert "same_frozen_holdout" in result["failed_checks"]


def test_runner_rejects_source_mutation_and_generated_stub(tmp_path: Path) -> None:
    baseline = _arm(tmp_path, "baseline", {"recognition_accuracy": 0.8})
    candidate = _arm(
        tmp_path, "candidate", {"recognition_accuracy": 0.9},
        source_snapshot_after="sha256:" + "f" * 64,
        generated_stub_count=1,
    )

    result = run_baseline_candidate_experiment(
        root=tmp_path, queue=_queue(), candidate_digest=DIGEST,
        baseline_receipt=baseline, candidate_receipt=candidate,
    )

    assert result["status"] == "blocked"
    assert "source_snapshots_unchanged" in result["failed_checks"]
    assert "generated_stub_gate" in result["failed_checks"]


def test_runner_does_not_run_without_queue_authority(tmp_path: Path) -> None:
    baseline = _arm(tmp_path, "baseline", {"recognition_accuracy": 0.8})
    candidate = _arm(tmp_path, "candidate", {"recognition_accuracy": 0.9})

    result = run_baseline_candidate_experiment(
        root=tmp_path,
        queue={"status": "waiting_for_candidate", "ready": []},
        candidate_digest=DIGEST,
        baseline_receipt=baseline,
        candidate_receipt=candidate,
    )

    assert result["status"] == "blocked"
    assert "queue_candidate_ready" in result["failed_checks"]
