from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from runtime.memory_index import MemoryIndex
from runtime.registry import CapabilityRegistry
from runtime.template_instantiator import TemplateInstantiationError, plan_from_memory_template


def _copy_runtime_contract_files(source: Path, target: Path) -> None:
    shutil.copytree(source / "plugins", target / "plugins")
    shutil.copytree(source / "registry", target / "registry")


def _write_success_report(root: Path, goal_id: str) -> None:
    reports = root / "artifacts" / "goals" / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    report = {
        "goal_id": goal_id,
        "goal": "Normalize input text from $input.text and then hash the normalized text.",
        "summary": "Goal executed successfully through nodes: normalize_text, hash_payload",
        "status": "decided",
        "level4_decision": {"action": "PLAN_WITH_L35"},
        "level35_plan": {
            "pipeline": {
                "id": f"pipeline_{goal_id}",
                "version": "1.0",
                "nodes": [
                    {"id": "normalize_text", "capability": "normalize_text", "input": {"text": "$input.text"}},
                    {
                        "id": "hash_payload",
                        "capability": "hash_payload",
                        "input": {"value": "$nodes.normalize_text.output.text"},
                    },
                ],
                "edges": [["normalize_text", "hash_payload"]],
                "retry_policy": {"max_attempts": 1, "retry_on": ["transient"]},
            }
        },
        "execution": {"status": "ok", "completed_nodes": ["normalize_text", "hash_payload"]},
    }
    (reports / f"{goal_id}.json").write_text(json.dumps(report), encoding="utf-8")


def _write_failed_report(root: Path, goal_id: str) -> None:
    reports = root / "artifacts" / "goals" / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    report = {
        "goal_id": goal_id,
        "goal": "Normalize input text from $input.text and then hash the normalized text.",
        "summary": "Goal failed during template-shaped execution.",
        "status": "decided",
        "level4_decision": {"action": "PLAN_WITH_L35"},
        "level35_plan": {
            "pipeline": {
                "id": f"pipeline_{goal_id}",
                "version": "1.0",
                "nodes": [
                    {"id": "normalize_text", "capability": "normalize_text", "input": {"text": "$input.text"}},
                    {
                        "id": "hash_payload",
                        "capability": "hash_payload",
                        "input": {"value": "$nodes.normalize_text.output.text"},
                    },
                ],
                "edges": [["normalize_text", "hash_payload"]],
                "retry_policy": {"max_attempts": 1, "retry_on": ["transient"]},
            }
        },
        "execution": {"status": "failed", "completed_nodes": ["normalize_text"]},
    }
    (reports / f"{goal_id}.json").write_text(json.dumps(report), encoding="utf-8")


def test_template_instantiator_builds_validated_plan(tmp_path):
    source = Path(__file__).resolve().parents[2]
    _copy_runtime_contract_files(source, tmp_path)
    _write_success_report(tmp_path, "goal_1")
    _write_success_report(tmp_path, "goal_2")
    registry = CapabilityRegistry(tmp_path)
    registry.load()
    index = MemoryIndex(tmp_path)
    index.rebuild()
    memory_preflight = index.search("normalize text and hash it")

    planned = plan_from_memory_template("normalize text and hash it", memory_preflight, registry)

    assert planned is not None
    assert planned["planner"] == "memory_template"
    assert planned["pipeline"]["nodes"][0]["capability"] == "normalize_text"


def test_template_instantiator_rejects_required_capability_mismatch(tmp_path):
    source = Path(__file__).resolve().parents[2]
    _copy_runtime_contract_files(source, tmp_path)
    registry = CapabilityRegistry(tmp_path)
    registry.load()
    _write_success_report(tmp_path, "goal_1")
    _write_success_report(tmp_path, "goal_2")
    memory = MemoryIndex(tmp_path)
    memory.rebuild()
    memory_preflight = memory.search("normalize text and hash it", limit=3)

    with pytest.raises(TemplateInstantiationError, match="do not match"):
        plan_from_memory_template(
            "Convert markdown file to RTF file",
            memory_preflight,
            registry,
            required_capabilities=["read_text_file", "markdown_to_rtf", "write_text_file"],
        )


def test_template_recommendation_requires_mature_template(tmp_path):
    source = Path(__file__).resolve().parents[2]
    _copy_runtime_contract_files(source, tmp_path)
    _write_success_report(tmp_path, "goal_1")
    index = MemoryIndex(tmp_path)
    payload = index.rebuild()
    memory_preflight = index.search("normalize text and hash it")

    assert payload["templates"][0]["safety_status"] == "immature"
    assert memory_preflight["template_recommendation"] is None


def test_template_failure_blocks_recommendation(tmp_path):
    source = Path(__file__).resolve().parents[2]
    _copy_runtime_contract_files(source, tmp_path)
    _write_success_report(tmp_path, "goal_1")
    _write_success_report(tmp_path, "goal_2")
    _write_failed_report(tmp_path, "goal_3")
    index = MemoryIndex(tmp_path)
    payload = index.rebuild()
    memory_preflight = index.search("normalize text and hash it")

    assert payload["templates"][0]["safety_status"] == "blocked_by_failures"
    assert payload["templates"][0]["failure_count"] == 1
    assert memory_preflight["template_recommendation"] is None


def test_template_instantiator_rejects_degraded_capability(tmp_path):
    source = Path(__file__).resolve().parents[2]
    _copy_runtime_contract_files(source, tmp_path)
    _write_success_report(tmp_path, "goal_1")
    _write_success_report(tmp_path, "goal_2")
    registry = CapabilityRegistry(tmp_path)
    registry.load()
    registry.mark_status("hash_payload", "degraded", reason="test")
    index = MemoryIndex(tmp_path)
    index.rebuild()
    memory_preflight = index.search("normalize text and hash it")

    with pytest.raises(TemplateInstantiationError, match="not active"):
        plan_from_memory_template("normalize text and hash it", memory_preflight, registry)


def test_goal_run_prefers_valid_memory_template_without_llm(tmp_path):
    source = Path(__file__).resolve().parents[2]
    _copy_runtime_contract_files(source, tmp_path)
    _write_success_report(tmp_path, "goal_1")
    _write_success_report(tmp_path, "goal_2")
    MemoryIndex(tmp_path).rebuild()

    with patch("runtime.llm_graph_planner.plan_pipeline_with_llm", side_effect=AssertionError("LLM should not be called")):
        from tools.goal_run import main

        with patch.object(
            sys,
            "argv",
            [
                "goal_run.py",
                "--root",
                str(tmp_path),
                "--goal",
                "Normalize input text from $input.text and then hash the normalized text.",
                "--execute",
                "--input-json",
                '{"text":"template path"}',
            ],
        ):
            assert main() == 0

    reports = sorted((tmp_path / "artifacts" / "goals" / "reports").glob("goal_*.json"))
    newest = json.loads(reports[-1].read_text(encoding="utf-8"))
    assert newest["level35_plan"]["planner"] == "memory_template"
    assert newest["execution"]["status"] == "ok"


def test_memory_instantiate_cli(tmp_path):
    source = Path(__file__).resolve().parents[2]
    _copy_runtime_contract_files(source, tmp_path)
    _write_success_report(tmp_path, "goal_1")
    _write_success_report(tmp_path, "goal_2")

    result = subprocess.run(
        [
            sys.executable,
            str(source / "tools" / "memory_instantiate.py"),
            "--root",
            str(tmp_path),
            "--goal",
            "normalize text and hash it",
            "--rebuild",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload["planner"] == "memory_template"
    assert payload["pipeline"]["nodes"][0]["capability"] == "normalize_text"
