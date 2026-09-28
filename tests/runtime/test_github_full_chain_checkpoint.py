from __future__ import annotations

from pathlib import Path

from tools.github_full_chain_checkpoint import run_case_batch


def test_case_batch_checkpoints_and_resumes_completed_projects(tmp_path: Path):
    projects = tmp_path / "projects"
    for name in ("alpha", "beta"):
        (projects / name / ".git").mkdir(parents=True)
    checkpoint = tmp_path / "checkpoint.json"
    calls: list[str] = []

    def runner(project: Path) -> dict:
        calls.append(project.name)
        return {"project": project.name, "status": "ok"}

    first = run_case_batch(projects_dir=projects, runner=runner, checkpoint_path=checkpoint)
    second = run_case_batch(
        projects_dir=projects, runner=runner, checkpoint_path=checkpoint, resume=True
    )

    assert [case["project"] for case in first] == ["alpha", "beta"]
    assert [case["project"] for case in second] == ["alpha", "beta"]
    assert calls == ["alpha", "beta"]


def test_case_batch_isolates_project_exception(tmp_path: Path):
    project = tmp_path / "projects" / "broken"
    (project / ".git").mkdir(parents=True)

    cases = run_case_batch(
        projects_dir=project.parent,
        runner=lambda path: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    assert cases[0]["status"] == "needs_review"
    assert cases[0]["executor"]["executor_status"] == "evaluation_error"
    assert "RuntimeError: boom" in cases[0]["evaluation_error"]


def test_case_batch_runs_only_recognition_qualified_project_names(tmp_path: Path):
    projects = tmp_path / "projects"
    for name in ("qualified", "rejected"):
        (projects / name / ".git").mkdir(parents=True)

    cases = run_case_batch(
        projects_dir=projects,
        runner=lambda path: {"project": path.name, "status": "ok"},
        project_names={"qualified"},
    )

    assert [case["project"] for case in cases] == ["qualified"]
