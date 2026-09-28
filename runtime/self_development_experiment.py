"""Compare baseline and candidate outcomes before L0/L1 staging."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .evidence_ledger import verify_evidence_entry


ALLOWED_CLASSES = {"L0", "L1"}


def evaluate_self_development_experiment(
    *,
    change_class: str,
    target_metric: str,
    baseline: dict[str, float],
    candidate: dict[str, float],
    generated_stub_count: int,
    evidence_root: Path,
    evaluation_receipt: str,
    minimum_improvement: float = 0.01,
) -> dict[str, Any]:
    dimensions = sorted(set(baseline) | set(candidate))
    receipt = verify_evidence_entry(root=evidence_root, ledger_path=Path(evaluation_receipt))
    payload = dict(receipt.get("evidence_payload") or {})
    receipt_gates = dict(payload.get("checks") or {})
    comparisons = {
        name: {
            "baseline": baseline.get(name),
            "candidate": candidate.get(name),
            "delta": _delta(baseline.get(name), candidate.get(name)),
            "regressed": _regressed(baseline.get(name), candidate.get(name)),
        }
        for name in dimensions
    }
    target = comparisons.get(target_metric, {})
    checks = {
        "bounded_change_class": change_class in ALLOWED_CLASSES,
        "target_metric_present": target_metric in baseline and target_metric in candidate,
        "target_improved": float(target.get("delta") or 0.0) >= minimum_improvement,
        "no_metric_regression": all(not row["regressed"] for row in comparisons.values()),
        "no_generated_function_stubs": generated_stub_count == 0,
        "ledger_receipt_verified": receipt.get("status") == "verified",
        "independent_holdout": receipt_gates.get("independent_holdout") is True,
        "independent_evaluator": receipt_gates.get("independent_evaluator") is True,
        "no_role_regression": receipt_gates.get("no_role_regression") is True,
        "generated_stub_gate": receipt_gates.get("generated_stub_gate") is True
        and int(payload.get("generated_stub_count") or 0) == 0,
    }
    passed = all(checks.values())
    body = {
        "artifact_type": "SelfDevelopmentExperiment",
        "schema_version": "self_development_experiment.v1",
        "status": "staging_eligible" if passed else "rejected",
        "change_class": change_class,
        "target_metric": target_metric,
        "minimum_improvement": minimum_improvement,
        "comparisons": comparisons,
        "generated_stub_count": generated_stub_count,
        "evaluation_receipt": evaluation_receipt,
        "checks": checks,
        "failed_checks": [name for name, value in checks.items() if not value],
        "active_apply_authorized": False,
        "promotion_applied": False,
    }
    return {**body, "experiment_digest": _digest(body)}


def verify_self_development_experiment(
    experiment: dict[str, Any], *, evidence_root: Path | None = None
) -> bool:
    body = {key: value for key, value in experiment.items() if key != "experiment_digest"}
    structurally_valid = (
        experiment.get("artifact_type") == "SelfDevelopmentExperiment"
        and experiment.get("status") == "staging_eligible"
        and experiment.get("experiment_digest") == _digest(body)
        and experiment.get("active_apply_authorized") is False
        and experiment.get("promotion_applied") is False
    )
    if not structurally_valid or evidence_root is None:
        return structurally_valid
    receipt = verify_evidence_entry(
        root=evidence_root,
        ledger_path=Path(str(experiment.get("evaluation_receipt") or "")),
    )
    payload = dict(receipt.get("evidence_payload") or {})
    checks = dict(payload.get("checks") or {})
    return (
        receipt.get("status") == "verified"
        and checks.get("independent_holdout") is True
        and checks.get("independent_evaluator") is True
        and checks.get("no_role_regression") is True
        and checks.get("generated_stub_gate") is True
        and int(payload.get("generated_stub_count") or 0) == 0
    )


def _delta(before: float | None, after: float | None) -> float | None:
    if not isinstance(before, (int, float)) or not isinstance(after, (int, float)):
        return None
    return round(float(after) - float(before), 6)


def _regressed(before: float | None, after: float | None) -> bool:
    return not isinstance(before, (int, float)) or not isinstance(after, (int, float)) or float(after) < float(before)


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
