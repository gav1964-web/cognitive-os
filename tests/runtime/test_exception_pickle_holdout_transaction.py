import json
from pathlib import Path

from runtime.exception_pickle_holdout_transaction import (
    run_exception_pickle_holdout_transaction,
)


def _write_report(path: Path) -> None:
    path.write_text(
        json.dumps({
            "implementation_result": {
                "status": "verified_in_sandbox",
                "semantic_verification": {"status": "passed"},
                "project_native_verification": {
                    "status": "passed",
                    "targeted_replay": {"status": "passed"},
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
    for index in range(3):
        _write_report(root / f"report-{index}.json")
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
                    "project": f"used-{index}",
                    "target": f"pkg.py:Used{index}.__init__",
                    "report": f"report-{index}.json",
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
    candidates = []
    for index in range(4):
        project = root / f"holdout-{index}"
        project.mkdir()
        candidates.append({
            "canonical_project": f"holdout-{index}",
            "project_root": project.name,
            "path": "pkg.py",
            "class_name": f"Holdout{index}Error",
            "score": 7,
            "required_constructor_parameters": ["value"],
            "stored_constructor_parameters": ["value"],
            "pickle_test_signals": [],
        })
    candidates.append({
        "canonical_project": "used-0",
        "project_root": ".",
        "path": "pkg.py",
        "class_name": "Used0",
        "score": 10,
        "required_constructor_parameters": ["value"],
        "stored_constructor_parameters": ["value"],
    })
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "scan": {"untouched_holdout_scanned": False},
            "candidates": candidates,
        }),
        encoding="utf-8",
    )
    return ledger, audit


def test_holdout_transaction_uses_independent_applicable_candidates(tmp_path: Path):
    ledger, audit = _fixture(tmp_path)

    report = run_exception_pickle_holdout_transaction(
        root=tmp_path,
        ledger_path=ledger,
        audit_path=audit,
        regression_passed=True,
        config_doctor_passed=True,
    )

    assert report["status"] == "holdout_ready"
    assert report["holdout_candidate_count"] == 4
    assert {row["project"] for row in report["holdout_candidates"]} >= {
        "holdout-0",
        "holdout-1",
        "holdout-2",
    }
    assert all(row["project"] != "used-0" for row in report["holdout_candidates"])
    assert report["kb_promotion"] is False


def test_holdout_transaction_blocks_without_regression(tmp_path: Path):
    ledger, audit = _fixture(tmp_path)

    report = run_exception_pickle_holdout_transaction(
        root=tmp_path,
        ledger_path=ledger,
        audit_path=audit,
        regression_passed=False,
        config_doctor_passed=True,
    )

    assert report["status"] == "blocked"
    assert report["failed_checks"] == ["regression_tests"]
