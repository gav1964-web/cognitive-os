import json
from pathlib import Path

from runtime.exception_pickle_promotion_transaction import (
    promote_exception_pickle_reconstruction,
)


def _fixture(root: Path) -> tuple[Path, Path, Path, Path]:
    readiness = root / "readiness.json"
    readiness.write_text(
        json.dumps({
            "artifact_type": "ExceptionPicklePromotionReadiness",
            "status": "eligible_for_promotion_review",
            "promotion_review_allowed": True,
            "autonomous_activation_allowed": True,
            "kb_promotion_allowed": False,
            "evidence": {
                "reports": [{"project": "used", "target": "pkg.py:Used.__init__"}],
                "autonomous_reports": [{
                    "project": "holdout",
                    "target": "pkg.py:HoldoutError.__init__",
                    "verified": True,
                }],
                "supervised_verified_count": 3,
                "autonomous_verified_count": 1,
            },
        }),
        encoding="utf-8",
    )
    evaluator = root / "evaluator.json"
    evaluator.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleIndependentEvaluatorReview",
            "status": "passed",
            "evidence": {"autonomous_project": "holdout"},
            "source_apply": False,
            "kb_promotion": False,
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
        }),
        encoding="utf-8",
    )
    catalog = root / "knowledge/role_knowledge/exception_pickle_reconstruction_patterns.json"
    return readiness, evaluator, holdout, catalog


def test_exception_pickle_promotion_writes_catalog_after_approval(tmp_path: Path):
    readiness, evaluator, holdout, catalog = _fixture(tmp_path)

    report = promote_exception_pickle_reconstruction(
        root=tmp_path,
        readiness_path=readiness,
        evaluator_review_path=evaluator,
        holdout_path=holdout,
        explicit_approval=True,
        regression_passed=True,
        config_doctor_passed=True,
    )

    payload = json.loads(catalog.read_text(encoding="utf-8"))
    assert report["status"] == "promoted"
    assert payload["status"] == "active"
    assert payload["operator"]["status"] == "validated_active"
    assert payload["safety"]["source_apply_allowed"] is False


def test_exception_pickle_promotion_blocks_without_approval_and_keeps_catalog_absent(
    tmp_path: Path,
):
    readiness, evaluator, holdout, catalog = _fixture(tmp_path)

    report = promote_exception_pickle_reconstruction(
        root=tmp_path,
        readiness_path=readiness,
        evaluator_review_path=evaluator,
        holdout_path=holdout,
        explicit_approval=False,
        regression_passed=True,
        config_doctor_passed=True,
    )

    assert report["status"] == "blocked"
    assert report["failed_checks"] == ["explicit_approval"]
    assert not catalog.exists()
