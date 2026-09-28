"""Standalone pytest plugin copied into the qualification control directory."""

from __future__ import annotations

import json
import os
from pathlib import Path


_REPORT = {"schema_version": "historical_pytest_result.v1", "collected": [],
           "reports": [], "collection_errors": []}


def pytest_collection_finish(session):
    _REPORT["collected"] = [item.nodeid for item in session.items]


def pytest_collectreport(report):
    if report.failed:
        _REPORT["collection_errors"].append(str(report.longrepr)[-2000:])


def pytest_runtest_logreport(report):
    crash = getattr(report.longrepr, "reprcrash", None)
    _REPORT["reports"].append({
        "nodeid": report.nodeid, "phase": report.when, "outcome": report.outcome,
        "wasxfail": bool(getattr(report, "wasxfail", False)),
        "message": str(getattr(crash, "message", ""))[:2000],
    })


def pytest_sessionfinish(session, exitstatus):
    _REPORT["exit_code"] = int(exitstatus)
    path = Path(os.environ["COGNITIVE_OS_HISTORICAL_REPORT_PATH"])
    path.write_text(json.dumps(_REPORT, ensure_ascii=False), encoding="utf-8")
