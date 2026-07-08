from __future__ import annotations

from pathlib import Path

from runtime.programmer_prompt_curriculum import run_programmer_prompt_curriculum
from runtime.greenfield_scaffold import create_greenfield_scaffold


def test_programmer_prompt_curriculum_reports_greenfield_gaps():
    root = Path(__file__).resolve().parents[2]
    report = run_programmer_prompt_curriculum(
        root=root,
        curriculum_dir=root / "curricula" / "programmer_prompt_local_3",
        write=False,
    )

    assert report["status"] == "needs_improvement"
    assert report["case_count"] == 3
    assert report["invariants"]["teacher_reference_is_ground_truth"] is False
    assert report["summary"]["verdicts"]["prompt_intake_only"] == 3
    assert "greenfield_project_scaffold" in report["summary"]["top_backlog"]
    assert "code_file_generation" in report["summary"]["top_backlog"]


def test_ixbt_case_keeps_live_network_out_of_default_tests():
    root = Path(__file__).resolve().parents[2]
    report = run_programmer_prompt_curriculum(
        root=root,
        curriculum_dir=root / "curricula" / "programmer_prompt_local_3",
        write=False,
    )
    ixbt = next(case for case in report["cases"] if case["case"] == "ixbt_news_scraper")

    assert ixbt["current_system_trace"]["source_code_changes"] is False
    assert ixbt["current_system_trace"]["intent"] == "implementation"
    assert ixbt["gap_analysis"]["project_scoped_verification_missing"] is True
    assert "live access is optional and not required for default tests" in ixbt["gap_analysis"]["missing_acceptance"]


def test_programmer_prompt_curriculum_can_emit_greenfield_scaffold(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    report = run_programmer_prompt_curriculum(
        root=tmp_path,
        curriculum_dir=root / "curricula" / "programmer_prompt_local_3",
        write=True,
    )
    ixbt = next(case for case in report["cases"] if case["case"] == "ixbt_news_scraper")
    project_dir = Path(ixbt["current_system_trace"]["scaffold"]["project_dir"])

    assert project_dir.is_dir()
    assert (project_dir / "pyproject.toml").is_file()
    assert (project_dir / "tests" / "fixtures" / "ixbt_news.html").is_file()
    assert ixbt["gap_analysis"]["greenfield_generation_missing"] is False
    assert ixbt["gap_analysis"]["fixture_tests_missing"] is False
    assert ixbt["gap_analysis"]["missing_artifacts"] == []
    assert ixbt["gap_analysis"]["project_scoped_verification_missing"] is False
    assert ixbt["current_system_trace"]["verification"]["status"] == "passed"
    assert ixbt["gap_analysis"]["code_generation_missing"] is False
    assert "parser works from fixture without network" in ixbt["current_system_trace"]["acceptance_covered"]
    assert "greenfield_project_scaffold" not in report["summary"]["top_backlog"]
    assert "code_file_generation" not in report["summary"]["top_backlog"]
    assert "dependency_policy" not in report["summary"]["top_backlog"]


def test_programmer_prompt_curriculum_local_10_is_ready(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    report = run_programmer_prompt_curriculum(
        root=tmp_path,
        curriculum_dir=root / "curricula" / "programmer_prompt_local_10",
        write=True,
    )

    assert report["status"] == "ok"
    assert report["case_count"] == 10
    assert report["summary"]["verdicts"] == {"programmer_ready": 10}
    assert report["summary"]["top_backlog"] == []
    for case in report["cases"]:
        assert case["current_system_trace"]["verification"]["status"] == "passed"
        assert case["gap_analysis"]["missing_artifacts"] == []
        assert case["gap_analysis"]["missing_acceptance"] == []


def test_greenfield_scaffold_rejects_escaping_paths(tmp_path: Path):
    reference = {
        "prompt": "bad",
        "expected_artifacts": ["../escape.py"],
    }

    try:
        create_greenfield_scaffold(root=tmp_path, case_name="bad", reference=reference)
    except ValueError as exc:
        assert "escapes scaffold root" in str(exc)
    else:
        raise AssertionError("expected escaping scaffold artifact to be rejected")
