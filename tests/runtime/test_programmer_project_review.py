from __future__ import annotations

from pathlib import Path

from runtime.programmer_project_review import run_programmer_project_review


def test_programmer_project_review_generates_code_and_tester_opinion(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    report = run_programmer_project_review(
        root=tmp_path,
        curriculum_dir=root / "curricula" / "programmer_prompt_local_10",
        case_name="json_log_filter_cli",
        write=True,
    )
    tester_review = report["tester_review"]
    project_dir = Path(report["programmer_artifact"]["project_dir"])

    assert report["status"] == "ok"
    assert project_dir.is_dir()
    assert (project_dir / "src" / "json_log_filter" / "filter.py").is_file()
    assert (project_dir / "tests" / "test_core.py").is_file()
    assert tester_review["artifact_type"] == "TesterProjectReview"
    assert tester_review["role"] == "tester"
    assert tester_review["recommendation"] in {"approve", "approve_with_risks"}
    assert tester_review["checks"]["verification_passed"] is True
    assert tester_review["checks"]["acceptance_complete"] is True
    assert tester_review["checks"]["has_negative_or_edge_test"] is True
    assert tester_review["checks"]["cli_uses_argparse"] is True
    assert tester_review["checks"]["cli_accepts_input_output"] is True
    assert tester_review["checks"]["readme_behavior_aligned"] is True
    assert tester_review["coverage"]["missing_acceptance"] == []
    assert tester_review["coverage"]["edge_evidence"]
    assert report["report_path"].endswith(".json")


def test_programmer_project_review_rejects_unknown_case(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]

    try:
        run_programmer_project_review(
            root=tmp_path,
            curriculum_dir=root / "curricula" / "programmer_prompt_local_10",
            case_name="missing_case",
        )
    except FileNotFoundError as exc:
        assert "unknown programmer curriculum case" in str(exc)
    else:
        raise AssertionError("expected unknown case to fail")
