from pathlib import Path

from runtime.project_change_trial import (
    FeatureNeedle,
    TrialFile,
    build_trial_report,
    compare_text_files,
    copy_optional_files,
    create_fixture,
    create_trial_dir,
    trial_invariants,
    write_report,
)


def test_project_change_trial_helpers_build_fixture_and_compare(tmp_path: Path) -> None:
    source_project = tmp_path / "project"
    source_project.mkdir()
    baseline = source_project / "tool.py.bak.0"
    teacher = source_project / "tool.py"
    baseline.write_text("MODEL = 'local'\n", encoding="utf-8")
    teacher.write_text("MODEL = 'remote'\nTOKEN_ENV = 'API_TOKEN'\n", encoding="utf-8")
    (source_project / "requirements.txt").write_text("requests\n", encoding="utf-8")

    out_dir = create_trial_dir(tmp_path, "change_trials", "trial")
    fixture = create_fixture(out_dir, "fixture", [TrialFile("tool.py", baseline)])
    copied = copy_optional_files(source_project, fixture, ["requirements.txt", "missing.txt"])
    (fixture / "tool.py").write_text(teacher.read_text(encoding="utf-8"), encoding="utf-8")

    comparison = compare_text_files(
        teacher_path=teacher,
        result_path=fixture / "tool.py",
        feature_needles=[
            FeatureNeedle("remote_model", present=("remote",)),
            FeatureNeedle("local_removed", absent=("local",)),
        ],
    )
    report = build_trial_report(
        artifact_type="GenericProjectChangeTrial",
        status="ok",
        source_project=source_project,
        trial_fixture=fixture,
        teacher_file=teacher,
        baseline_sources=[baseline],
        sections={"comparison": comparison, "optional_files_copied": copied},
    )
    path = write_report(report, out_dir, "trial.json")

    assert copied == ["requirements.txt"]
    assert comparison["exact_match"] is True
    assert comparison["feature_score"] == 2
    assert report["teacher_reference"]["quality"] == "teacher_reference_not_ground_truth"
    assert report["invariants"] == trial_invariants()
    assert path.is_file()
