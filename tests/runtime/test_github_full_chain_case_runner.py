from tools.github_full_chain_case_runner import run_case_with_timeout
from tools.github_full_chain_report import markdown


def test_case_runner_returns_complete_timeout_case(tmp_path):
    project = tmp_path / "slow-project"
    project.mkdir()

    case = run_case_with_timeout(
        project,
        root=tmp_path,
        run_executor=False,
        run_verification=False,
        timeout_seconds=0,
    )

    assert case["status"] == "needs_review"
    assert case["quality_score"] == 0.0
    assert case["target_chain"] == {}
    assert case["failed_checks"] == [{"code": "evaluation_case_timeout", "passed": False}]


def test_markdown_accepts_timeout_case_without_optional_fields():
    text = markdown({
        "milestone": "timeout-probe",
        "generated_at": "now",
        "project_count": 1,
        "summary": {"worst_case_score": 0.0, "ready_by_worst_case": False, "needs_review": 1},
        "cases": [{
            "project": "slow-project",
            "status": "needs_review",
            "quality_score": 0.0,
            "failed_checks": [{"code": "evaluation_case_timeout", "passed": False}],
        }],
    })

    assert "evaluation_case_timeout" in text
    assert "targets: `{}`" in text
