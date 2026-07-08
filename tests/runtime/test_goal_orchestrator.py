from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from runtime.goal_orchestrator import decide_goal_route, decide_goal_route_with_llm
from runtime.goal_session import GoalSessionStore
from runtime.registry import CapabilityRegistry


def test_goal_orchestrator_routes_known_goal_to_l35():
    root = Path(__file__).resolve().parents[2]
    registry = CapabilityRegistry(root)
    registry.reset_from_plugins()

    decision = decide_goal_route("Normalize input text and hash it", registry)

    assert decision.action == "PLAN_WITH_L35"
    assert decision.required_capabilities == ["normalize_text", "hash_payload"]


def test_goal_orchestrator_asks_for_clarification_on_vague_goal():
    root = Path(__file__).resolve().parents[2]
    registry = CapabilityRegistry(root)
    registry.reset_from_plugins()

    decision = decide_goal_route("help me", registry)

    assert decision.action == "ASK_CLARIFICATION"
    assert decision.clarification_question


def test_goal_orchestrator_requests_capability_for_missing_tooling():
    root = Path(__file__).resolve().parents[2]
    registry = CapabilityRegistry(root)
    registry.reset_from_plugins()

    registry.mark_status("translate_text", "retired", reason="test_missing_translate")

    decision = decide_goal_route("Translate this text to German", registry)

    assert decision.action == "REQUEST_CAPABILITY_SPEC"
    assert decision.missing_capability_hint == "translate_text"


def test_goal_orchestrator_routes_translation_when_capability_exists():
    root = Path(__file__).resolve().parents[2]
    registry = CapabilityRegistry(root)
    registry.reset_from_plugins()

    decision = decide_goal_route("Translate this text to German", registry)

    assert decision.action == "PLAN_WITH_L35"
    assert decision.required_capabilities == ["translate_text"]


def test_goal_orchestrator_routes_project_analysis_when_capability_exists():
    root = Path(__file__).resolve().parents[2]
    registry = CapabilityRegistry(root)
    registry.reset_from_plugins()

    decision = decide_goal_route("Analyze project map", registry)

    assert decision.action == "PLAN_WITH_L35"
    assert decision.required_capabilities == [
        "scan_project_tree",
        "detect_project_stack",
        "read_many_files",
        "extract_python_structure",
        "extract_runtime_commands",
        "project_map_report",
    ]


def test_goal_orchestrator_requests_pdf_capability_when_missing():
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="cos_missing_pdf_") as temp_dir:
        temp_root = Path(temp_dir)
        shutil.copytree(root / "plugins", temp_root / "plugins")
        shutil.copytree(root / "registry", temp_root / "registry")
        plugin_dir = temp_root / "plugins" / "parse_pdf"
        if plugin_dir.exists():
            shutil.rmtree(plugin_dir)
        registry = CapabilityRegistry(temp_root)
        registry.reset_from_plugins()

        decision = decide_goal_route("Parse a PDF file from $input.path", registry)

    assert decision.action == "REQUEST_CAPABILITY_SPEC"
    assert decision.missing_capability_hint == "parse_pdf"


def test_goal_run_cli_returns_clarification_without_llm_call():
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, str(root / "tools" / "goal_run.py"), "--root", str(root), "--goal", "help me"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["level4_decision"]["action"] == "ASK_CLARIFICATION"
    assert payload["level4_deliberation"]["recommendation"] == "return_route_decision"
    assert payload["goal_id"].startswith("goal_")
    assert "memory_preflight" in payload
    assert Path(payload["report_path"]).exists()


def test_goal_session_accepts_clarification(tmp_path):
    store = GoalSessionStore(tmp_path)
    session = store.create("help me")

    store.add_clarification(session, "Normalize text and hash it")
    reloaded = store.load(session["goal_id"])

    assert reloaded["clarifications"][0]["answer"] == "Normalize text and hash it"
    assert "Clarification:" in reloaded["goal"]
    assert reloaded["effective_goal"] == "Normalize text and hash it"


def test_goal_run_cli_requests_capability_spec():
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="cos_missing_capability_") as temp_dir:
        temp_root = Path(temp_dir)
        shutil.copytree(root / "plugins", temp_root / "plugins")
        shutil.copytree(root / "registry", temp_root / "registry")
        registry = CapabilityRegistry(temp_root)
        registry.load()
        registry.mark_status("translate_text", "retired", reason="test_missing_translate")
        result = subprocess.run(
            [
                sys.executable,
                str(root / "tools" / "goal_run.py"),
                "--root",
                str(temp_root),
                "--goal",
                "Translate this text to German",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(result.stdout)

        assert payload["level4_decision"]["action"] == "REQUEST_CAPABILITY_SPEC"
        assert Path(payload["capability_spec_request"]["spec"]).exists()


def test_goal_orchestrator_can_use_llm_for_route_decision():
    root = Path(__file__).resolve().parents[2]
    registry = CapabilityRegistry(root)
    registry.reset_from_plugins()
    response = {
        "action": "ASK_CLARIFICATION",
        "reason_code": "MODEL_NEEDS_INPUT",
        "required_capabilities": [],
        "missing_capability_hint": None,
        "clarification_question": "What input should be used?",
    }

    with patch("runtime.goal_orchestrator.call_json_chat", return_value=response):
        decision = decide_goal_route_with_llm("process it", registry)

    assert decision.action == "ASK_CLARIFICATION"
    assert decision.reason_code == "GOAL_INTAKE_MISSING_REQUIRED_FIELDS"


def test_goal_orchestrator_sanitizes_noisy_llm_plan_decision():
    root = Path(__file__).resolve().parents[2]
    registry = CapabilityRegistry(root)
    registry.reset_from_plugins()
    response = {
        "action": "PLAN_WITH_L35",
        "reason_code": "MODEL_ROUTE",
        "required_capabilities": ["normalize_text", "hash_payload"],
        "missing_capability_hint": "These capabilities are missing.",
        "clarification_question": "What text should be used?",
    }

    with patch("runtime.goal_orchestrator.call_json_chat", return_value=response) as call:
        decision = decide_goal_route_with_llm("Normalize input text from $input.text and hash it", registry)

    assert decision.action == "PLAN_WITH_L35"
    assert decision.required_capabilities == ["normalize_text", "hash_payload"]
    assert decision.missing_capability_hint is None
    assert decision.clarification_question is None
    assert "GoalSpec:" in call.call_args.args[0][1]["content"]
    assert "field_confidence" in call.call_args.args[0][1]["content"]


def test_goal_orchestrator_rejects_llm_plan_with_missing_capability():
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="cos_llm_missing_pdf_") as temp_dir:
        temp_root = Path(temp_dir)
        shutil.copytree(root / "plugins", temp_root / "plugins")
        shutil.copytree(root / "registry", temp_root / "registry")
        plugin_dir = temp_root / "plugins" / "parse_pdf"
        if plugin_dir.exists():
            shutil.rmtree(plugin_dir)
        registry = CapabilityRegistry(temp_root)
        registry.reset_from_plugins()
        response = {
            "action": "PLAN_WITH_L35",
            "reason_code": "MODEL_ROUTE",
            "required_capabilities": ["parse_pdf"],
            "missing_capability_hint": None,
            "clarification_question": None,
        }

        with patch("runtime.goal_orchestrator.call_json_chat", return_value=response):
            decision = decide_goal_route_with_llm("Parse a PDF file from $input.path", registry)

    assert decision.action == "REQUEST_CAPABILITY_SPEC"
    assert decision.missing_capability_hint == "parse_pdf"
