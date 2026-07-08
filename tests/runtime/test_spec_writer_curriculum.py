from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from runtime.spec_writer_curriculum import run_spec_writer_curriculum


ROOT = Path(__file__).resolve().parents[2]


def test_spec_writer_curriculum_local_three_scores_teacher_references():
    report = run_spec_writer_curriculum(
        root=ROOT,
        curriculum_dir=ROOT / "curricula" / "spec_writer_local_3",
        write=True,
    )

    assert report["status"] == "ok"
    assert report["project_count"] == 3
    assert report["summary"]["score"] == 1.0
    assert report["summary"]["backlog_items"] == 0
    assert report["invariants"]["teacher_reference_is_ground_truth"] is False
    assert report["invariants"]["automatic_code_changes_from_own_output"] is False
    assert report["invariants"]["implementer_tester_reviewer_not_in_scope"] is True
    assert Path(report["report_path"]).exists()


def test_spec_writer_curriculum_cli_writes_report():
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "spec_writer_curriculum.py"),
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
    assert payload["summary"]["score"] == 1.0
    assert Path(payload["report_path"]).exists()


def test_spec_writer_curriculum_external_three_when_projects_exist():
    curriculum_dir = ROOT / "curricula" / "spec_writer_external_local_3"
    refs = list(curriculum_dir.glob("*/teacher_reference.json"))
    if not refs or not all(Path(json.loads(path.read_text(encoding="utf-8"))["project_dir"]).exists() for path in refs):
        pytest.skip("external local projects are not available")

    report = run_spec_writer_curriculum(root=ROOT, curriculum_dir=curriculum_dir, write=False)

    assert report["status"] == "ok"
    assert report["milestone"] == "SpecWriter Curriculum External-3 v0.1"
    assert report["project_count"] == 3
    assert report["summary"]["score"] == 1.0
    assert report["summary"]["backlog_items"] == 0


def test_spec_writer_curriculum_rejects_ground_truth_reference(tmp_path):
    case_dir = tmp_path / "bad_case"
    project_dir = case_dir / "source"
    project_dir.mkdir(parents=True)
    (case_dir / "teacher_reference.json").write_text(
        json.dumps(
            {
                "schema_version": "spec_writer_curriculum.v1",
                "project_dir": project_dir.as_posix(),
                "teacher_profile": "spec_writer",
                "reference_quality": "ground_truth",
                "expected_spec": {},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="reference_quality='teacher_reference_not_ground_truth'"):
        run_spec_writer_curriculum(root=ROOT, curriculum_dir=tmp_path)
