from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from runtime.architect_curriculum import run_architect_curriculum


ROOT = Path(__file__).resolve().parents[2]


def test_architect_curriculum_local_three_scores_teacher_references():
    report = run_architect_curriculum(
        root=ROOT,
        curriculum_dir=ROOT / "curricula" / "architect_local_3",
        write=True,
    )

    assert report["status"] == "ok"
    assert report["project_count"] == 3
    assert report["summary"]["fact_recall"] >= 0.9
    assert report["summary"]["fact_precision"] >= 0.75
    assert report["summary"]["judgment_score"] >= 0.8
    assert report["invariants"]["teacher_reference_is_ground_truth"] is False
    assert report["invariants"]["facts_and_judgments_scored_separately"] is True
    assert report["invariants"]["automatic_code_changes_from_own_output"] is False
    assert Path(report["report_path"]).exists()


def test_architect_curriculum_cli_writes_report():
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "architect_curriculum.py"),
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
    assert payload["summary"]["judgment_score"] >= 0.8
    assert Path(payload["report_path"]).exists()


def test_architect_curriculum_external_three_reports_teacher_review_when_projects_exist():
    curriculum_dir = ROOT / "curricula" / "architect_external_local_3"
    refs = list(curriculum_dir.glob("*/teacher_reference.json"))
    if not refs or not all(Path(json.loads(path.read_text(encoding="utf-8"))["project_dir"]).exists() for path in refs):
        pytest.skip("external local projects are not available")

    report = run_architect_curriculum(root=ROOT, curriculum_dir=curriculum_dir, write=False)

    assert report["status"] == "ok"
    assert report["project_count"] == 3
    assert report["summary"]["tooling_targets"]["core_first_source_weighting"] >= 2
    assert all(case["teacher_review"]["expected_architect_behavior"] for case in report["cases"])


def test_architect_curriculum_rejects_ground_truth_reference(tmp_path):
    case_dir = tmp_path / "bad_case"
    project_dir = case_dir / "source"
    project_dir.mkdir(parents=True)
    (case_dir / "teacher_reference.json").write_text(
        json.dumps(
            {
                "schema_version": "architect_curriculum.v1",
                "project_dir": project_dir.as_posix(),
                "teacher_profile": "architect",
                "reference_quality": "ground_truth",
                "facts": {},
                "judgments": {},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="reference_quality='teacher_reference_not_ground_truth'"):
        run_architect_curriculum(root=ROOT, curriculum_dir=tmp_path)
