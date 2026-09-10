from runtime.project_development_boundary_field_trial import run_boundary_field_trial
from runtime.contract_registry import ContractRegistry


def test_boundary_field_trial_passes_train_and_blind_source_cases() -> None:
    report = run_boundary_field_trial()

    assert report["status"] == "passed"
    assert report["summary"] == {
        "case_count": 6,
        "passed": 6,
        "accuracy": 1.0,
        "blind_case_count": 2,
        "independent_lineage_count": 6,
    }
    assert report["promotion"]["status"] == "not_promoted"
    assert report["promotion"]["kb_promotion_evidence"] is False
    ContractRegistry({}).validate_artifact(report)


def test_boundary_field_trial_can_run_blind_split_separately() -> None:
    report = run_boundary_field_trial(split="blind")

    assert report["status"] == "passed"
    assert report["summary"]["case_count"] == 2
    assert report["summary"]["blind_case_count"] == 2
    assert all(row["split"] == "blind" for row in report["cases"])
