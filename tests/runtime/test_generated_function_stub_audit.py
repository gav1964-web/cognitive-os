from __future__ import annotations

import json
from pathlib import Path

from runtime.generated_function_stub_audit import build_generated_function_stub_audit


def _write_report(path: Path, admission: dict | None) -> None:
    case = {"project": "demo"}
    if admission is not None:
        case["generated_function_stub_admission"] = admission
    path.write_text(json.dumps({"cases": [case]}), encoding="utf-8")


def test_stub_audit_binds_clean_admissions_to_report_digest(tmp_path: Path) -> None:
    report = tmp_path / "holdout.json"
    _write_report(report, {
        "artifact_type": "GeneratedFunctionStubAdmission",
        "status": "passed",
        "violations": [],
        "parse_failures": [],
    })

    audit = build_generated_function_stub_audit([report])

    assert audit["status"] == "passed"
    assert audit["generated_stub_count"] == 0
    assert list(audit["report_digests"]) == [report.resolve().as_posix()]


def test_stub_audit_fails_closed_for_missing_admission(tmp_path: Path) -> None:
    report = tmp_path / "holdout.json"
    _write_report(report, None)

    audit = build_generated_function_stub_audit([report])

    assert audit["status"] == "blocked"
    assert audit["failed_checks"] == ["all_cases_have_admission"]
