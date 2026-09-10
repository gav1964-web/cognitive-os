from __future__ import annotations

import json
from pathlib import Path

import pytest

from runtime.three_route_evaluation import (
    ROUTES,
    build_blind_bundle,
    freeze_manifest,
    manifest_drift_errors,
    protocol_status,
    validate_manifest,
    validate_receipt,
)
from runtime.three_route_evaluation_scoring import score_blind_evaluation
from runtime.evaluation_protocol_policy import evaluation_protocol_policy_errors


POLICY = {
    "routes": list(ROUTES),
    "route_contracts": {
        "direct_agent": {"forbidden_executors": ["deterministic_direct_baseline"], "may_use_cognitive_os": False},
        "short_chain": {"may_use_cognitive_os": True},
        "full_chain": {"may_use_cognitive_os": True},
    },
    "rubric": {
        "requirement_coverage": 0.3, "correctness": 0.3, "maintainability": 0.15,
        "evidence_quality": 0.15, "safety": 0.1,
    },
    "winner_margin": 0.25,
    "minimum_tasks_before_claim": 1,
    "minimum_tasks_per_class_before_claim": 1,
    "product_task_classes": ["cli_utility"],
    "require_independent_judge": True,
    "require_judge_route_separation": True,
    "require_blind_key_withheld_until_scored": True,
    "require_same_model_per_task": True,
}


def test_freeze_manifest_binds_full_task_and_prompt(tmp_path: Path) -> None:
    task = _task(tmp_path)
    manifest = freeze_manifest(tmp_path, source_commit="abc")

    assert task.name == manifest["tasks"][0]["task_id"]
    assert manifest["routes"] == list(ROUTES)
    assert manifest["tasks"][0]["constraints"] == ["No network."]
    assert manifest["tasks"][0]["success_criteria"] == ["Output works."]
    assert validate_manifest(manifest) == []

    manifest["tasks"][0]["task_class"] = "tampered"
    assert validate_manifest(manifest) == ["manifest_digest_mismatch"]


def test_manifest_drift_detects_input_tree_mutation(tmp_path: Path) -> None:
    task = _task(tmp_path)
    source = tmp_path / "source"
    source.mkdir()
    (source / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    (task / "input.json").write_text(
        json.dumps({"kind": "project_tree", "path": "source"}), encoding="utf-8"
    )
    manifest = freeze_manifest(tmp_path, source_commit="abc")

    assert manifest_drift_errors(tmp_path, manifest) == []
    (source / "module.py").write_text("VALUE = 2\n", encoding="utf-8")

    assert manifest_drift_errors(tmp_path, manifest) == ["task_snapshot_drift:task01_demo"]


def test_protocol_policy_rejects_self_scoring_escape_hatches() -> None:
    policy = json.loads((Path(__file__).resolve().parents[2] / "config" / "evaluation_protocol_v2.json").read_text(encoding="utf-8"))
    assert evaluation_protocol_policy_errors(policy) == []

    policy["route_contracts"]["direct_agent"]["forbidden_executors"] = []
    policy["rubric"]["correctness"] = 0.1
    errors = evaluation_protocol_policy_errors(policy)
    assert "legacy_proxy_not_forbidden" in errors
    assert "rubric_weight_sum" in errors


def test_receipt_rejects_proxy_and_prompt_mismatch(tmp_path: Path) -> None:
    _task(tmp_path)
    manifest = freeze_manifest(tmp_path, source_commit="abc")
    receipt = _receipt(manifest, "direct_agent")
    receipt["executor"] = "deterministic_direct_baseline"
    receipt["prompt_digest"] = "wrong"

    errors = validate_receipt(receipt, manifest, POLICY)

    assert "forbidden_route_executor" in errors
    assert "prompt_digest_mismatch" in errors


def test_bundle_requires_all_routes_and_redacts_identity(tmp_path: Path) -> None:
    _task(tmp_path)
    manifest = freeze_manifest(tmp_path, source_commit="abc")
    receipts = [_receipt(manifest, route) for route in ROUTES]

    bundle, key = build_blind_bundle(manifest, receipts, POLICY)

    encoded = json.dumps(bundle)
    assert "cognitive_os" not in encoded
    assert "direct_agent" not in encoded
    assert len(bundle["candidates"]) == 3
    assert len(key["mapping"]) == 3
    second_bundle, _ = build_blind_bundle(manifest, receipts, POLICY)
    assert {row["candidate_id"] for row in bundle["candidates"]} != {
        row["candidate_id"] for row in second_bundle["candidates"]
    }
    assert protocol_status(manifest, receipts, POLICY)["claim_eligible"] is True

    with pytest.raises(ValueError, match="missing_receipt"):
        build_blind_bundle(manifest, receipts[:2], POLICY)


def test_independent_scorecard_unblinds_only_after_complete_scoring(tmp_path: Path) -> None:
    _task(tmp_path)
    manifest = freeze_manifest(tmp_path, source_commit="abc")
    receipts = [_receipt(manifest, route) for route in ROUTES]
    bundle, key = build_blind_bundle(manifest, receipts, POLICY)
    scores = []
    for index, candidate in enumerate(bundle["candidates"]):
        value = 7 + index
        scores.append({
            "task_id": candidate["task_id"], "candidate_id": candidate["candidate_id"],
            "rubric": {name: value for name in POLICY["rubric"]}, "blocking_findings": [],
        })
    scorecard = {
        "bundle_digest": bundle["bundle_digest"],
        "judge": {
            "id": "independent-reviewer", "independent": True,
            "produced_route_output": False, "saw_blind_key_before_scoring": False,
        },
        "scores": scores,
    }

    report = score_blind_evaluation(
        bundle=bundle, blind_key=key, scorecard=scorecard, receipts=receipts, policy=POLICY
    )

    assert report["status"] == "evaluated"
    assert report["claim_eligible"] is True
    assert report["task_results"][0]["winner"] in ROUTES
    assert report["operations_by_route"]["direct_agent"]["runs"] == 1

    scorecard["judge"]["independent"] = False
    with pytest.raises(ValueError, match="independent_judge_required"):
        score_blind_evaluation(
            bundle=bundle, blind_key=key, scorecard=scorecard, receipts=receipts, policy=POLICY
        )


def _task(root: Path) -> Path:
    task = root / "evaluation" / "task01_demo"
    task.mkdir(parents=True)
    (task / "prompt.md").write_text(
        "# Prompt\n\n## Original Prompt\n\nBuild it.\n\n## Constraints\n\n- No network.\n\n"
        "## Success Criteria\n\n- Output works.\n",
        encoding="utf-8",
    )
    (task / "metrics.json").write_text(json.dumps({"task_class": "cli_utility"}), encoding="utf-8")
    return task


def _receipt(manifest: dict, route: str) -> dict:
    task = manifest["tasks"][0]
    return {
        "artifact_type": "ThreeRouteExecutionReceipt",
        "task_id": task["task_id"], "route": route,
        "manifest_digest": manifest["manifest_digest"], "prompt_digest": task["prompt_digest"],
        "input_digest": task["input_digest"],
        "status": "completed", "executor": f"real-{route}", "model": "same-model",
        "runtime_seconds": 1.0, "estimated_cost": 0.01,
        "token_usage": {"input": 10, "output": 20}, "manual_corrections": [],
        "acceptance_checks": [{"id": "works", "passed": True, "evidence": "test"}],
        "artifacts": [{"path": "result.txt", "digest": "sha256:" + "2" * 64}],
        "judge_payload": {"summary": f"{route} result", "executor": "must disappear"},
        "safety": {"source_mutation_detected": False},
        "uses_cognitive_os": route != "direct_agent",
    }
