from __future__ import annotations

from pathlib import Path

from runtime.project_failure_evidence_packet import (
    attach_failure_evidence_packets,
    build_failure_evidence_packet,
)


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    (project / "pkg").mkdir(parents=True)
    (project / "tests").mkdir()
    (project / "pkg" / "parser.py").write_text(
        "def parse_value(value: str) -> str:\n"
        "    return value.split(':', 1)[1]\n",
        encoding="utf-8",
    )
    (project / "tests" / "test_parser.py").write_text(
        "from pkg.parser import parse_value\n\n"
        "def test_empty_value():\n"
        "    assert parse_value('') == ''\n",
        encoding="utf-8",
    )
    return project


def _failure() -> dict:
    return {
        "target": "pkg/parser.py:parse_value",
        "authority": "failing_contract_test",
        "detail": "1 failed",
        "failure_signature": "stable-digest",
        "failing_nodeids": ["tests/test_parser.py::test_empty_value"],
    }


def _chain_case() -> dict:
    repetition = {
        "failure_signature": "stable-digest",
        "leaf_production_target": "pkg/parser.py:parse_value",
        "production_targets": ["pkg/parser.py:parse_value"],
        "exit_code": 1,
        "output_tail": (
            "FAILED tests/test_parser.py::test_empty_value\n"
            "E   IndexError: list index out of range\n"
            "E   assert parse_value('') == ''\n"
        ),
    }
    return {"repetitions": [dict(repetition), dict(repetition)]}


def test_packet_binds_stable_failure_target_and_test_source(tmp_path: Path) -> None:
    packet = build_failure_evidence_packet(
        project_dir=_project(tmp_path), failure=_failure(), chain_case=_chain_case()
    )

    assert packet["status"] == "complete"
    assert packet["reproduction"]["matching_repetitions"] == 2
    assert "IndexError" in packet["observed_failure"]
    assert "def test_empty_value" in packet["test_sources"][0]["excerpt"]
    assert "def parse_value" in packet["target_source"]["excerpt"]
    assert packet["packet_digest"].startswith("sha256:")
    assert packet["execution_authorized"] is False


def test_packet_rejects_test_path_outside_project(tmp_path: Path) -> None:
    project = _project(tmp_path)
    failure = _failure()
    failure["failing_nodeids"] = ["../outside.py::test_escape"]

    packet = build_failure_evidence_packet(
        project_dir=project, failure=failure, chain_case=_chain_case()
    )

    assert packet["test_sources"] == []
    assert packet["status"] == "partial"
    assert packet["checks"]["failing_test_source_is_present"] is False


def test_packet_is_attached_without_mutating_diagnosis(tmp_path: Path) -> None:
    diagnosis = {"issues": [{"failure_evidence": [_failure()]}]}

    result = attach_failure_evidence_packets(
        diagnosis, project_dir=_project(tmp_path), chain_case=_chain_case()
    )

    assert result["issues"][0]["failure_evidence_packet"]["status"] == "complete"
    assert "failure_evidence_packet" not in diagnosis["issues"][0]
