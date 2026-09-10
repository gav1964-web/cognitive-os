from __future__ import annotations

import json
from pathlib import Path

import pytest

from runtime.self_development_collector import (
    SelfDevelopmentCollectorError,
    collect_project_development_report,
)


def _report(root: Path) -> Path:
    directory = root / "artifacts" / "project_development"
    directory.mkdir(parents=True)
    path = directory / "project_development_new.json"
    path.write_text(json.dumps({
        "artifact_type": "ProjectDevelopmentRun",
        "generated_at": "2026-08-31T00:00:00+00:00",
        "project": "new-project",
    }), encoding="utf-8")
    return path


def test_collector_runs_detector_once_and_checkpoints_digest(monkeypatch, tmp_path: Path) -> None:
    path = _report(tmp_path)
    calls = []

    def detect(**kwargs):
        calls.append(kwargs)
        return {
            "status": "waiting_for_evidence",
            "candidate_count": 0,
            "report_path": "artifacts/self_development/detection.json",
        }

    monkeypatch.setattr("runtime.self_development_collector.run_prospective_detection", detect)

    first = collect_project_development_report(root=tmp_path, report_path=path)
    second = collect_project_development_report(root=tmp_path, report_path=path)

    assert first["status"] == "collected"
    assert first["detector_run"] is True
    assert second["status"] == "duplicate_ignored"
    assert second["detector_run"] is False
    assert len(calls) == 1
    checkpoint = json.loads((tmp_path / first["checkpoint"]).read_text(encoding="utf-8"))
    assert list(checkpoint["processed"]) == ["artifacts/project_development/project_development_new.json"]
    assert checkpoint["safety"]["promotion_applied"] is False


def test_collector_rejects_report_outside_owned_directory(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    path.write_text(json.dumps({"artifact_type": "ProjectDevelopmentRun"}), encoding="utf-8")

    with pytest.raises(SelfDevelopmentCollectorError, match="reports only"):
        collect_project_development_report(root=tmp_path, report_path=path)
