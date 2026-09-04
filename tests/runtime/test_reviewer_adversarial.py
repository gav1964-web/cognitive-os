from pathlib import Path

from runtime.reviewer_adversarial import run_reviewer_adversarial_trial


ROOT = Path(__file__).resolve().parents[2]


def test_reviewer_detects_all_adversarial_artifact_mutations() -> None:
    report = run_reviewer_adversarial_trial(root=ROOT)

    assert report["status"] == "ok"
    assert report["summary"] == {"case_count": 6, "passed": 6, "failed": 0}
    assert all(case["recommendation"] == "request_rework" for case in report["cases"])
    assert report["invariants"]["source_code_changes"] is False
