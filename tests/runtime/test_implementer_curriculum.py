from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from runtime.implementer_curriculum import run_implementer_curriculum


ROOT = Path(__file__).resolve().parents[2]


def test_implementer_curriculum_local_three_scores_teacher_references():
    report = run_implementer_curriculum(
        root=ROOT,
        curriculum_dir=ROOT / "curricula" / "implementer_local_3",
        write=True,
    )

    assert report["status"] == "ok"
    assert report["milestone"] == "Implementer Curriculum Local-3 v0.1"
    assert report["project_count"] == 3
    assert report["summary"]["score"] == 1.0
    assert report["summary"]["avg_score"] == 1.0
    assert report["summary"]["worst_case_score"] == 1.0
    assert report["summary"]["ready_threshold"] == 0.92
    assert report["summary"]["ready_by_worst_case"] is True
    assert report["summary"]["backlog_items"] == 0
    assert report["invariants"]["teacher_reference_is_ground_truth"] is False
    assert report["invariants"]["source_code_changes"] is False
    assert report["invariants"]["registry_changes"] is False
    assert report["invariants"]["foundry_or_promote_not_in_scope"] is True
    assert Path(report["report_path"]).exists()


def test_implementer_curriculum_cli_writes_report():
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "implementer_curriculum.py"),
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
    assert payload["summary"]["worst_case_score"] == 1.0
    assert payload["summary"]["ready_by_worst_case"] is True
    assert Path(payload["report_path"]).exists()


@pytest.mark.local_corpus
def test_implementer_curriculum_reports_current_external_measurement():
    curriculum_dir = ROOT / "curricula" / "implementer_external_local_3"
    refs = list(curriculum_dir.glob("*/teacher_reference.json"))
    if not refs or not all(Path(json.loads(path.read_text(encoding="utf-8"))["project_dir"]).exists() for path in refs):
        pytest.skip("external local projects are not available")

    report = run_implementer_curriculum(root=ROOT, curriculum_dir=curriculum_dir, write=False)

    assert report["milestone"] == "Implementer Curriculum External-3 v0.1"
    assert report["project_count"] == 3
    # These external worktrees change independently of COS. Test that the
    # measurement reports failures honestly, not that live projects always
    # reproduce a dated teacher score. Frozen local cases above retain 1.0 gates.
    scores = [case['score']['score'] for case in report['cases']]
    assert report['summary']['worst_case_score'] == min(scores)
    assert report['summary']['ready_threshold'] == 0.92
    assert report['summary']['ready_by_worst_case'] == (min(scores) >= 0.92)
    gaps = [gap for case in report['cases'] for gap in case['improvement_backlog']]
    assert report['summary']['backlog_items'] == len(gaps)
    ready = not gaps and min(scores) >= 0.92
    assert report['status'] == ('ok' if ready else 'needs_improvement')
    for case in report["cases"]:
        candidate = case["actual"]["candidate"]
        actions = case["actual"]["implementation_actions"]
        assert any(candidate in action for action in actions)
        assert all(" only inside writable_scope" not in action or candidate in action for action in actions)


def test_missing_required_evidence_remains_a_reported_quality_failure():
    from runtime.implementer_curriculum import _report, _score_plan, _improvement_backlog
    reference = ROOT / 'curricula/implementer_local_3'
    baseline = run_implementer_curriculum(root=ROOT, curriculum_dir=reference)
    case = baseline['cases'][0]
    actual = dict(case['actual'])
    actual['evidence_scope'] = []
    expected = json.loads((reference / case['case'] / 'teacher_reference.json').read_text(encoding='utf-8'))['expected_plan']
    score = _score_plan(expected, actual)
    assert score['checks']['required_evidence_scope_covered'] is False
    gaps = _improvement_backlog(score)
    assert {'type': 'IMPLEMENTER_GAP', 'check': 'required_evidence_scope_covered'} in gaps
    result = _report([{**case, 'score': score, 'status': 'needs_improvement',
                       'improvement_backlog': gaps}], curriculum_dir=reference)
    assert result['status'] == 'needs_improvement'
    assert result['summary']['backlog_items'] >= 1


def test_implementer_curriculum_rejects_ground_truth_reference(tmp_path):
    case_dir = tmp_path / "bad_case"
    project_dir = case_dir / "source"
    project_dir.mkdir(parents=True)
    (case_dir / "teacher_reference.json").write_text(
        json.dumps(
            {
                "schema_version": "implementer_curriculum.v1",
                "project_dir": project_dir.as_posix(),
                "teacher_profile": "implementer",
                "reference_quality": "ground_truth",
                "expected_plan": {},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="reference_quality='teacher_reference_not_ground_truth'"):
        run_implementer_curriculum(root=ROOT, curriculum_dir=tmp_path)
