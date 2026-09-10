from __future__ import annotations

import json
from pathlib import Path

from runtime.evidence_ledger import promote_evidence
from runtime.self_development_experiment import (
    evaluate_self_development_experiment,
    verify_self_development_experiment,
)


def _receipt(root: Path, *, stub_count: int = 0) -> str:
    source = root / "experiment_evidence.json"
    source.write_text(json.dumps({
        "artifact_type": "SelfDevelopmentExperimentEvidence",
        "status": "passed",
        "checks": {
            "independent_holdout": True,
            "independent_evaluator": True,
            "no_role_regression": True,
            "generated_stub_gate": stub_count == 0,
        },
        "generated_stub_count": stub_count,
    }), encoding="utf-8")
    entry = promote_evidence(
        root=root,
        source=source,
        producer_fingerprint="candidate-runner:v1",
        evaluator_fingerprint="blind-evaluator:v1",
        replay_command=["python", "tools/self_development_trial.py"],
    )
    return str(entry["ledger_path"])


def _experiment(root: Path, **overrides):
    values = {
        "change_class": "L1",
        "target_metric": "recognition_accuracy",
        "baseline": {"recognition_accuracy": 0.91, "role_continuity": 1.0},
        "candidate": {"recognition_accuracy": 0.94, "role_continuity": 1.0},
        "generated_stub_count": 0,
        "evidence_root": root,
        "evaluation_receipt": _receipt(root),
    }
    values.update(overrides)
    return evaluate_self_development_experiment(**values)


def test_bounded_experiment_can_become_staging_eligible(tmp_path: Path):
    experiment = _experiment(tmp_path)

    assert experiment["status"] == "staging_eligible"
    assert verify_self_development_experiment(experiment) is True
    assert experiment["active_apply_authorized"] is False


def test_any_metric_regression_rejects_experiment(tmp_path: Path):
    experiment = _experiment(
        tmp_path,
        candidate={"recognition_accuracy": 0.95, "role_continuity": 0.99},
    )

    assert experiment["status"] == "rejected"
    assert "no_metric_regression" in experiment["failed_checks"]


def test_generated_function_stub_rejects_experiment(tmp_path: Path):
    experiment = _experiment(tmp_path, generated_stub_count=1)

    assert experiment["status"] == "rejected"
    assert "no_generated_function_stubs" in experiment["failed_checks"]


def test_structural_change_cannot_use_bounded_experiment_route(tmp_path: Path):
    experiment = _experiment(tmp_path, change_class="L3")

    assert experiment["status"] == "rejected"
    assert "bounded_change_class" in experiment["failed_checks"]
