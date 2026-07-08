from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from runtime.memory_index import MemoryIndex


def _write_report(root: Path, filename: str, payload: dict) -> None:
    reports = root / "artifacts" / "goals" / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / filename).write_text(json.dumps(payload), encoding="utf-8")


def test_memory_index_rebuilds_and_searches_reports(tmp_path):
    _write_report(
        tmp_path,
        "goal_1.json",
        {
            "goal_id": "goal_1",
            "goal": "Normalize text and hash it",
            "summary": "Goal executed successfully through nodes: normalize, hash",
            "status": "decided",
            "level4_decision": {"action": "PLAN_WITH_L35"},
            "level35_plan": {
                "pipeline": {
                    "id": "normalize_hash",
                    "nodes": [
                        {"capability": "normalize_text"},
                        {"capability": "hash_payload"},
                    ],
                }
            },
            "execution": {"status": "ok", "completed_nodes": ["normalize", "hash"]},
        },
    )

    index = MemoryIndex(tmp_path)
    payload = index.rebuild()
    result = index.search("hash normalized text")

    assert len(payload["entries"]) == 1
    assert result["matches"][0]["goal_id"] == "goal_1"
    assert result["recommendation"]["action"] == "CONSIDER_REUSE_PREVIOUS_PLAN"


def test_memory_cli_rebuild_and_search(tmp_path):
    _write_report(
        tmp_path,
        "goal_1.json",
        {
            "goal_id": "goal_1",
            "goal": "List files in a directory",
            "summary": "Goal executed successfully through nodes: list",
            "status": "decided",
            "level4_decision": {"action": "PLAN_WITH_L35"},
            "level35_plan": {"pipeline": {"id": "list_files", "nodes": [{"capability": "list_files"}]}},
            "execution": {"status": "ok", "completed_nodes": ["list"]},
        },
    )
    root = Path(__file__).resolve().parents[2]

    rebuild = subprocess.run(
        [sys.executable, str(root / "tools" / "memory_rebuild.py"), "--root", str(tmp_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    search = subprocess.run(
        [sys.executable, str(root / "tools" / "memory_search.py"), "--root", str(tmp_path), "--query", "list directory files"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(rebuild.stdout)["entries"] == 1
    assert json.loads(search.stdout)["matches"][0]["goal_id"] == "goal_1"


def test_memory_index_builds_plan_templates_from_successful_reports(tmp_path):
    base = {
        "summary": "Goal executed successfully",
        "status": "decided",
        "level4_decision": {"action": "PLAN_WITH_L35"},
        "level35_plan": {
            "pipeline": {
                "id": "normalize_hash",
                "nodes": [
                    {"id": "normalize", "capability": "normalize_text", "input": {"text": "$input.text"}},
                    {"id": "hash", "capability": "hash_payload", "input": {"value": "$nodes.normalize.output.text"}},
                ],
                "edges": [["normalize", "hash"]],
                "retry_policy": {"max_attempts": 1},
            }
        },
        "execution": {"status": "ok", "completed_nodes": ["normalize", "hash"]},
    }
    _write_report(tmp_path, "goal_1.json", {"goal_id": "goal_1", "goal": "Normalize text and hash it", **base})
    _write_report(tmp_path, "goal_2.json", {"goal_id": "goal_2", "goal": "Clean text then hash payload", **base})

    index = MemoryIndex(tmp_path)
    payload = index.rebuild()
    result = index.search("normalize and hash text")

    assert len(payload["templates"]) == 1
    assert payload["templates"][0]["support_count"] == 2
    assert result["template_recommendation"]["action"] == "CONSIDER_REUSE_PLAN_TEMPLATE"
    assert result["template_recommendation"]["capabilities"] == ["normalize_text", "hash_payload"]


def test_memory_templates_cli_lists_derived_templates(tmp_path):
    _write_report(
        tmp_path,
        "goal_1.json",
        {
            "goal_id": "goal_1",
            "goal": "List files in a directory",
            "summary": "Goal executed successfully through nodes: list",
            "status": "decided",
            "level4_decision": {"action": "PLAN_WITH_L35"},
            "level35_plan": {
                "pipeline": {
                    "id": "list_files",
                    "nodes": [{"id": "list", "capability": "list_files", "input": {"path": "$input.path"}}],
                    "edges": [],
                }
            },
            "execution": {"status": "ok", "completed_nodes": ["list"]},
        },
    )
    root = Path(__file__).resolve().parents[2]

    result = subprocess.run(
        [sys.executable, str(root / "tools" / "memory_templates.py"), "--root", str(tmp_path), "--rebuild"],
        check=True,
        capture_output=True,
        text=True,
    )

    templates = json.loads(result.stdout)["templates"]
    assert templates[0]["capabilities"] == ["list_files"]
