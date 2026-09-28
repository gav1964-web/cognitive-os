import json
from pathlib import Path

from runtime.exception_pickle_independent_evaluator import review_exception_pickle_promotion


def _write_artifacts(root: Path, *, shadow_project: str = "holdout") -> tuple[Path, Path, Path]:
    readiness = root / "readiness.json"
    readiness.write_text(
        json.dumps({
            "artifact_type": "ExceptionPicklePromotionReadiness",
            "status": "eligible_for_promotion_review",
            "promotion_review_allowed": True,
            "kb_promotion_allowed": False,
            "checks": {"autonomous_evidence_available": True},
            "evidence": {
                "reports": [{"project": "used"}],
                "autonomous_reports": [{
                    "project": shadow_project,
                    "target": "pkg.py:HoldoutError.__init__",
                    "report": "shadow.json",
                    "verified": True,
                }],
            },
        }),
        encoding="utf-8",
    )
    holdout = root / "holdout.json"
    holdout.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleHoldoutTransaction",
            "status": "holdout_ready",
            "holdout_project_count": 25,
            "holdout_candidate_count": 25,
            "source_apply": False,
            "kb_promotion": False,
        }),
        encoding="utf-8",
    )
    shadow = root / "shadow.json"
    shadow.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleAutonomousShadowRun",
            "status": "autonomous_verified_shadow",
            "candidate": {
                "project": shadow_project,
                "target": "pkg.py:HoldoutError.__init__",
            },
            "operator_id": "preserve_exception_constructor_reconstruction",
            "counts_as_autonomous_verified_transformation": True,
            "project_native_semantic_replay": {"status": "passed"},
            "failed_checks": [],
            "source_apply": False,
            "kb_promotion": False,
        }),
        encoding="utf-8",
    )
    return readiness, holdout, shadow


def test_independent_evaluator_passes_complete_evidence(tmp_path: Path):
    readiness, holdout, shadow = _write_artifacts(tmp_path)

    report = review_exception_pickle_promotion(
        root=tmp_path,
        readiness_path=readiness,
        holdout_path=holdout,
        shadow_path=shadow,
    )

    assert report["status"] == "passed"
    assert report["failed_checks"] == []
    assert report["kb_promotion"] is False


def test_independent_evaluator_blocks_supervised_project_reuse(tmp_path: Path):
    readiness, holdout, shadow = _write_artifacts(tmp_path, shadow_project="used")

    report = review_exception_pickle_promotion(
        root=tmp_path,
        readiness_path=readiness,
        holdout_path=holdout,
        shadow_path=shadow,
    )

    assert report["status"] == "blocked"
    assert "shadow_project_independent" in report["failed_checks"]
