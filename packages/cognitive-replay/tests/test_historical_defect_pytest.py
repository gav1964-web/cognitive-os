from __future__ import annotations

import json
from pathlib import Path

import pytest

from cognitive_replay.pytest_report import pytest_status, read_test_report


def _report(root: Path, reports: list[dict], *, exit_code: int = 0, errors=None) -> dict:
    path = root / "report.json"
    path.write_text(json.dumps({
        "schema_version": "historical_pytest_result.v1", "exit_code": exit_code,
        "collected": ["tests/test_sample.py::test_value"], "reports": reports,
        "collection_errors": errors or [],
    }), encoding="utf-8")
    return {"returncode": exit_code, "structured": read_test_report(path, exit_code)}


def _phases(outcome: str = "passed", **extra) -> list[dict]:
    return [
        {"nodeid": "tests/test_sample.py::test_value", "phase": phase,
         "outcome": outcome if phase == "call" else "passed",
         **(extra if phase == "call" else {})}
        for phase in ("setup", "call", "teardown")
    ]


@pytest.mark.parametrize("mutation", ["missing_call", "missing_teardown", "duplicate", "uncollected"])
def test_incomplete_or_unbound_reports_cannot_pass(tmp_path: Path, mutation: str) -> None:
    phases = _phases()
    if mutation.startswith("missing"):
        phases = [row for row in phases if row["phase"] != mutation.removeprefix("missing_")]
    elif mutation == "duplicate":
        phases.append(dict(phases[1]))
    else:
        phases[1]["nodeid"] = "tests/test_elsewhere.py::test_other"
    run = _report(tmp_path, phases)
    run["stdout"] = "100 passed in 0.01s"

    assert pytest_status(run) == "environment_blocked"


@pytest.mark.parametrize("outcome,extra", [("skipped", {}), ("passed", {"wasxfail": True})])
def test_skipped_and_xpassed_nodes_do_not_count_as_passed(tmp_path: Path, outcome: str, extra: dict) -> None:
    run = _report(tmp_path, _phases(outcome, **extra))

    assert pytest_status(run) == "no_tests_executed"
    assert run["structured"]["passed"] == []


def test_teardown_failure_after_setup_skip_is_environment_error(tmp_path: Path) -> None:
    phases = _phases()
    phases[0]["outcome"] = "skipped"
    phases[2]["outcome"] = "failed"
    run = _report(tmp_path, [phases[0], phases[2]], exit_code=1)

    assert pytest_status(run) == "environment_blocked"


def test_collection_error_cannot_be_counted_as_a_defect(tmp_path: Path) -> None:
    run = _report(tmp_path, _phases("failed"), exit_code=1, errors=["missing fixture"])

    assert pytest_status(run) == "environment_blocked"


def test_runtime_missing_dependency_is_environment_error(tmp_path: Path) -> None:
    run = _report(tmp_path, _phases("failed", message="ModuleNotFoundError: dependency"), exit_code=1)

    assert pytest_status(run) == "environment_blocked"


def test_stdout_cannot_override_structured_outcomes(tmp_path: Path) -> None:
    run = _report(tmp_path, _phases("failed", message="assert 1 == 2"), exit_code=1)
    run["stdout"] = "10 passed"

    assert pytest_status(run) == "reproducible_failure"
    assert run["structured"]["failed"] == ["tests/test_sample.py::test_value"]


@pytest.mark.parametrize("payload", ["invalid json", "{}", '{"schema_version":"other"}'])
def test_invalid_report_is_controlled_failure(tmp_path: Path, payload: str) -> None:
    path = tmp_path / "report.json"
    path.write_text(payload, encoding="utf-8")

    assert read_test_report(path, 0)["status"] == "invalid"


def test_timeout_cannot_be_overridden_by_a_passing_report(tmp_path: Path) -> None:
    run = _report(tmp_path, _phases())
    run["returncode"] = 124

    assert pytest_status(run) == "timeout"
