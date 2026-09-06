from __future__ import annotations

import copy
import json
from pathlib import Path

from runtime.evidence_ledger import promote_evidence
from runtime.narrow_type_certification import verify_narrow_type_certification
from runtime.self_development_experiment_queue import build_self_development_experiment_queue
from runtime.self_development_prospective_detection import run_prospective_detection


ROOT = Path(__file__).resolve().parents[2]
CERTIFICATION_RECEIPT = "evidence/ledger/ca0bdda72697373d304b9a28923728612da25a58e09b4ad10e07c8f57f6bd657.json"


def test_current_corpus_routes_only_certified_candidates() -> None:
    detection = run_prospective_detection(root=ROOT, write=False)
    queue = build_self_development_experiment_queue(
        root=ROOT, detection=detection, certification_receipt=CERTIFICATION_RECEIPT
    )

    assert queue["status"] in {
        "waiting_for_candidate", "waiting_for_certified_candidate", "ready_for_experiment"
    }
    assert all(
        set(row["project_types"]).issubset({"cli_local_tool", "library_pure_transform"})
        for row in queue["ready"]
    )
    assert all(
        "project_type_not_certified" in row["reasons"]
        for row in queue["deferred"]
        if not set(row["project_types"]).issubset({"cli_local_tool", "library_pure_transform"})
    )
    assert queue["certification"]["project_strata"] == [
        "cli_local_tool", "library_pure_transform"
    ]
    assert all(queue["checks"].values())


def test_certified_candidate_is_bound_to_an_experiment_metric() -> None:
    detection = _detection("library_pure_transform")
    queue = build_self_development_experiment_queue(
        root=ROOT, detection=detection, certification_receipt=CERTIFICATION_RECEIPT
    )

    assert queue["status"] == "ready_for_experiment"
    assert queue["ready"][0]["target_metric"] == "recognition_accuracy"
    assert "unseen_project_holdout" in queue["ready"][0]["required_evidence"]


def test_uncertified_candidate_remains_deferred() -> None:
    queue = build_self_development_experiment_queue(
        root=ROOT,
        detection=_detection("framework_plugin_build"),
        certification_receipt=CERTIFICATION_RECEIPT,
    )

    assert queue["status"] == "waiting_for_certified_candidate"
    assert queue["ready_count"] == 0
    assert queue["deferred"][0]["reasons"] == ["project_type_not_certified"]


def test_tampered_certificate_is_rejected_even_inside_valid_ledger(tmp_path: Path) -> None:
    source = ROOT / "evidence" / "artifacts" / "d7042f071688b3dc6ce6ef29eb5a9cec8e788cc9a7192857a07fe9fabb9ddcac.json"
    certification = json.loads(source.read_text(encoding="utf-8"))
    certification["project_strata"].append("framework_plugin_build")
    assert verify_narrow_type_certification(certification) is False
    evidence = tmp_path / "tampered.json"
    evidence.write_text(json.dumps(certification), encoding="utf-8")
    receipt = promote_evidence(
        root=tmp_path,
        source=evidence,
        producer_fingerprint="test-producer:v1",
        evaluator_fingerprint="test-evaluator:v1",
        replay_command=["pytest"],
    )

    queue = build_self_development_experiment_queue(
        root=tmp_path,
        detection=_detection("library_pure_transform"),
        certification_receipt=str(receipt["ledger_path"]),
    )
    assert queue["status"] == "blocked"
    assert queue["checks"]["certification_receipt_verified"] is False


def test_detection_status_must_match_candidate_count() -> None:
    detection = _detection("library_pure_transform")
    detection["status"] = "waiting_for_evidence"

    queue = build_self_development_experiment_queue(
        root=ROOT, detection=detection, certification_receipt=CERTIFICATION_RECEIPT
    )

    assert queue["status"] == "blocked"
    assert queue["checks"]["detection_verified"] is False


def _detection(project_type: str) -> dict:
    source = run_prospective_detection(root=ROOT, write=False)
    candidate = {
        "signature": f"recognition_gap:classification:identity:{project_type}",
        "independent_project_count": 3,
        "dossier": {"proposal": {
            "proposal_id": "proposal-test",
            "classification": {"class": "L0"},
            "impact_map": {"project_types": [project_type]},
        }},
    }
    result = copy.deepcopy(source)
    result["status"] = "candidate_detected"
    result["candidate_count"] = 1
    result["candidates"] = [candidate]
    return result
