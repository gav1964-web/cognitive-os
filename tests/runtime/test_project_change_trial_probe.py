from pathlib import Path

from tools.project_change_trial_probe import run_probe


def test_project_change_trial_probe_is_fixture_only(tmp_path: Path) -> None:
    report = run_probe(root=tmp_path, write=True)

    assert report["status"] == "ok"
    assert report["scenario"]["id"] == "direct_provider_probe"
    assert report["comparison"]["exact_match"] is True
    assert report["comparison"]["feature_score"] == report["comparison"]["feature_total"]
    assert report["simulated_apply"]["source_project_unchanged"] is True
    assert report["invariants"]["fixture_only_apply"] is True
    assert report["invariants"]["teacher_reference_is_ground_truth"] is False
    assert Path(report["report_path"]).is_file()
