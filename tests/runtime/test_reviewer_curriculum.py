from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from runtime.reviewer_curriculum import run_reviewer_curriculum
from tools.github_reviewer_probe import _quality_score, _run_case


ROOT = Path(__file__).resolve().parents[2]


def test_reviewer_curriculum_local_three_scores_teacher_references():
    report = run_reviewer_curriculum(
        root=ROOT,
        curriculum_dir=ROOT / "curricula" / "reviewer_local_3",
        write=True,
    )

    assert report["status"] == "ok"
    assert report["milestone"] == "Reviewer Curriculum Local-3 v0.1"
    assert report["project_count"] == 3
    assert report["summary"]["worst_case_score"] >= 0.92
    assert report["summary"]["ready_by_worst_case"] is True
    assert report["summary"]["backlog_items"] == 0
    assert report["invariants"]["teacher_reference_is_ground_truth"] is False
    assert report["invariants"]["source_code_changes"] is False
    assert report["invariants"]["registry_changes"] is False
    assert report["invariants"]["foundry_or_promote_not_in_scope"] is True
    assert Path(report["report_path"]).exists()


def test_reviewer_curriculum_cli_writes_report():
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "reviewer_curriculum.py"),
            "--root",
            str(ROOT),
            "--write",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "ok"
    assert payload["summary"]["worst_case_score"] >= 0.92
    assert payload["summary"]["ready_by_worst_case"] is True
    assert Path(payload["report_path"]).exists()


def test_reviewer_curriculum_external_three_when_projects_exist():
    curriculum_dir = ROOT / "curricula" / "reviewer_external_local_3"
    refs = list(curriculum_dir.glob("*/teacher_reference.json"))
    if not refs or not all(Path(json.loads(path.read_text(encoding="utf-8"))["project_dir"]).exists() for path in refs):
        pytest.skip("external local projects are not available")

    report = run_reviewer_curriculum(root=ROOT, curriculum_dir=curriculum_dir, write=False)

    assert report["status"] == "ok"
    assert report["milestone"] == "Reviewer Curriculum External-3 v0.1"
    assert report["project_count"] == 3
    assert report["summary"]["worst_case_score"] >= 0.92
    assert report["summary"]["ready_by_worst_case"] is True
    assert report["summary"]["backlog_items"] == 0


def test_reviewer_curriculum_rejects_ground_truth_reference(tmp_path):
    case_dir = tmp_path / "bad_case"
    project_dir = case_dir / "source"
    project_dir.mkdir(parents=True)
    (case_dir / "teacher_reference.json").write_text(
        json.dumps(
            {
                "schema_version": "reviewer_curriculum.v1",
                "project_dir": project_dir.as_posix(),
                "teacher_profile": "reviewer",
                "reference_quality": "ground_truth",
                "expected_review": {},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="reference_quality='teacher_reference_not_ground_truth'"):
        run_reviewer_curriculum(root=ROOT, curriculum_dir=tmp_path)


def test_github_reviewer_probe_marks_rust_workspace_out_of_scope(tmp_path):
    project = tmp_path / "rust_workspace"
    (project / ".git").mkdir(parents=True)
    (project / "crates" / "core").mkdir(parents=True)
    (project / "python").mkdir()
    (project / "Cargo.toml").write_text("[workspace]\nmembers=['crates/core']\n", encoding="utf-8")
    for index in range(8):
        (project / "crates" / "core" / f"lib_{index}.rs").write_text("fn main() {}\n", encoding="utf-8")
    (project / "python" / "template.py").write_text("def helper():\n    return 'embedded'\n", encoding="utf-8")

    case = _run_case(project)

    assert case["status"] == "out_of_scope"
    assert case["source_code_changes"] is False
    assert "unsupported_primary_language" in case["blocked_reason"]


def test_github_reviewer_quality_score_is_capped_and_requires_binding():
    review = {
        "artifact_type": "ReviewFindings",
        "role": "reviewer",
        "contract_violations": [],
        "architecture_drift": [],
        "recommendation": "approve_with_risks",
        "forbidden_actions_observed": [],
    }
    coverage = {"target_covered": True, "scope_preserved": True}

    capped = _quality_score(
        review,
        "pkg/core.py:parse",
        "pkg/core.py:parse",
        "bound_to_extraction_contract",
        coverage,
        [],
    )
    weak = _quality_score(
        review,
        "pkg/core.py:parse",
        "pkg/core.py:parse",
        "",
        coverage,
        [],
    )

    assert capped == 1.0
    assert weak < 0.9
