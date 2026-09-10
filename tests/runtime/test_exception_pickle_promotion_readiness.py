import json
from pathlib import Path

from runtime.exception_pickle_promotion_readiness import (
    evaluate_exception_pickle_promotion_readiness,
)


def _write_case_report(path: Path, *, semantic: bool = True) -> None:
    path.write_text(
        json.dumps({
            "implementation_result": {
                "status": "verified_in_sandbox",
                **({"semantic_verification": {"status": "passed"}} if semantic else {}),
                "project_native_verification": {
                    "status": "passed",
                    "targeted_replay": {
                        "status": "passed",
                        "test_targets": ["tests/test_errors.py::test_pickle_error"],
                    },
                    "regression_suite": {"status": "passed"},
                },
                "stub_admission": {"status": "passed"},
                "source_invariant": {"unchanged": True},
                "source_apply": False,
                "memory_promotion": False,
            }
        }),
        encoding="utf-8",
    )


def _fixture(root: Path) -> tuple[Path, Path]:
    reports = []
    for index in range(3):
        report = root / f"report-{index}.json"
        _write_case_report(report)
        reports.append(report)
    ledger = root / "ledger.json"
    ledger.write_text(
        json.dumps({
            "artifact_type": "SupervisedTransferLedger",
            "status": "threshold_met",
            "target_count": 3,
            "verified_count": 3,
            "autonomous_verified_count": 0,
            "cases": [
                {
                    "project": f"project-{index}",
                    "target": f"pkg/errors.py:Error{index}.__init__",
                    "report": reports[index].name,
                    "status": "verified_in_sandbox",
                }
                for index in range(3)
            ],
            "safety": {
                "source_apply": False,
                "kb_promotion": False,
                "untouched_holdout_used": False,
            },
        }),
        encoding="utf-8",
    )
    audit = root / "audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "scan": {"untouched_holdout_scanned": False},
        }),
        encoding="utf-8",
    )
    return ledger, audit


def test_exception_pickle_promotion_readiness_allows_review_not_promotion(tmp_path: Path):
    ledger, audit = _fixture(tmp_path)

    report = evaluate_exception_pickle_promotion_readiness(
        root=tmp_path,
        ledger_path=ledger,
        audit_path=audit,
    )

    assert report["status"] == "eligible_for_promotion_review"
    assert report["promotion_review_allowed"] is True
    assert report["kb_promotion_allowed"] is False
    assert report["autonomous_activation_allowed"] is False
    assert "autonomous_evidence_available" in report["failed_checks"]


def test_exception_pickle_promotion_readiness_blocks_autonomy_without_autonomous_case(
    tmp_path: Path,
):
    ledger, audit = _fixture(tmp_path)

    report = evaluate_exception_pickle_promotion_readiness(
        root=tmp_path,
        ledger_path=ledger,
        audit_path=audit,
        require_autonomous_evidence=True,
    )

    assert report["status"] == "blocked"
    assert report["promotion_review_allowed"] is True
    assert report["autonomous_activation_allowed"] is False
    assert report["failed_checks"] == ["autonomous_evidence_available"]


def test_exception_pickle_promotion_readiness_accepts_legacy_pickle_native_replay(
    tmp_path: Path,
):
    ledger, audit = _fixture(tmp_path)
    _write_case_report(tmp_path / "report-0.json", semantic=False)

    report = evaluate_exception_pickle_promotion_readiness(
        root=tmp_path,
        ledger_path=ledger,
        audit_path=audit,
    )

    assert report["status"] == "eligible_for_promotion_review"
    assert report["evidence"]["reports"][0]["semantic_basis"] == "legacy_pickle_native_replay"
