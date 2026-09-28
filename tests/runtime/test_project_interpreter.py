from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch
import pytest
from runtime.project_deliberation import deliberate_project_report
from runtime.project_architecture_synthesis import load_architecture_knowledge, match_architecture_rule, synthesize_project_architecture
from runtime.project_facts import facts_from_project_report, llm_fact_digest
from runtime.project_interpreter import interpret_project_report
from runtime.project_tasks import generate_project_tasks
from runtime.project_signals import generate_project_signals
from runtime.local_inference import LocalInferenceConfig, LocalInferenceError
def _report() -> dict:
    return {
        "goal_id": "goal_test",
        "execution": {
            "outputs": {
                "project_map_report": {
                    "summary": {"root": "project", "frameworks": ["FastAPI"], "routes": 1},
                    "risks": [{"code": "risky_imports", "severity": "medium"}],
                    "answers": {
                        "1_scope": {"main_task": "Expose an API"},
                        "2_execution": {
                            "entrypoints": ["app/api/server.py"],
                            "central_flow_nodes": [{"path": "app/api/server.py", "name": "handle_chat", "call_count": 8}],
                            "internal_import_hubs": [{"path": "app/api/server.py", "internal_import_count": 5}],
                        },
                        "3_capabilities": {
                            "pure_transforms": [],
                            "too_broad_functions": [{"path": "app/api/server.py", "name": "handle_chat", "loc": 120}],
                        },
                        "4_contracts_data": {"explicit_schemas": [], "weak_contract_zones": ["app/api/server.py:health_check"]},
                        "5_errors_state_repro": {"minimal_cognitive_loop": ["call /health"]},
                        "6_runtime_extraction_readiness": {
                            "mixed_responsibility_functions": [
                                {
                                    "path": "app/api/server.py",
                                    "name": "handle_chat",
                                    "line": 10,
                                    "loc": 120,
                                    "responsibilities": ["io", "control_flow", "error_handling"],
                                }
                            ],
                            "hidden_orchestrators": [{"path": "app/api/server.py", "name": "handle_chat", "line": 10, "loc": 120, "call_count": 8}],
                            "idempotency_risks": [{"target": "app/api/server.py:handle_chat"}],
                            "quarantine_candidates": [{"target": "external_api"}],
                            "process_boundary_candidates": [{"target": "app/api/server.py:handle_chat"}],
                            "resume_reuse_plan": [{"step": "request_capture"}],
                            "minimal_extraction_plan": [{"capability": "app/api/server.py:handle_chat"}],
                        },
                    },
                },
                "extract_python_structure": {
                    "routes": [{"route": "/health", "methods": ["GET"]}],
                    "project_insights": {"test_surface": {"test_files": 1}, "external_imports": [{"module": "fastapi", "count": 1}]},
                },
                "extract_runtime_commands": {"commands": []},
            }
        },
    }

def test_project_signals_are_short_impulses():
    payload = {
        "signals": [
            {
                "type": "ENTRYPOINT_FOUND",
                "target": "app/api/server.py",
                "severity": "low",
                "suggested_action": "map_execution_path",
                "confidence": "high",
            }
        ],
        "confidence": "high",
    }
    with patch("runtime.project_signals.call_json_chat", return_value=payload):
        result = generate_project_signals(_report())

    assert result["layer"] == "L3.5"
    signal_types = {signal["type"] for signal in result["signals"]}
    assert "SUBSYSTEM_HOTSPOT" in signal_types
    assert "BROAD_FUNCTION" in signal_types
    assert "MIXED_RESPONSIBILITY" in signal_types
    assert "IDEMPOTENCY_RISK" in signal_types
    assert "ENTRYPOINT_FOUND" in signal_types
    assert result["deterministic_signal_count"] > 0
    assert result["fact_summary"]["frameworks"] == ["FastAPI"]


def test_project_signals_keep_deterministic_fallback_when_llm_fails():
    with patch("runtime.project_signals.call_json_chat", side_effect=LocalInferenceError("bad json")):
        result = generate_project_signals(_report())

    signal_types = {signal["type"] for signal in result["signals"]}
    assert result["source"] == "deterministic_fallback"
    assert "SUBSYSTEM_HOTSPOT" in signal_types
    assert "BROAD_FUNCTION" in signal_types
    assert "MIXED_RESPONSIBILITY" in signal_types
    assert result["fallback_reason"] == "bad json"


def test_project_deliberation_validates_human_contract():
    payload = {
        "executive_summary": "API service.",
        "capability_decomposition": ["health check"],
        "refactor_plan": ["split handlers"],
        "cognitive_loop": ["call /health"],
        "open_questions": [],
        "confidence": "high",
    }
    signals = {"signals": [{"type": "ENTRYPOINT_FOUND", "target": "app/api/server.py"}]}
    config = LocalInferenceConfig(
        base_url="https://provider.example/v1",
        model="large-cortex",
        provider_label="external_l4",
    )
    with patch("runtime.project_deliberation.call_json_chat", return_value=payload) as mocked:
        result = deliberate_project_report(_report(), level35_signals=signals, config=config)

    assert result["source"] == "external_l4"
    assert result["layer"] == "L4"
    assert result["executive_summary"] == "Expose an API"
    assert result["fact_summary"]["frameworks"] == ["FastAPI"]
    assert "external_imports" in mocked.call_args.args[0][1]["content"]


def test_project_deliberation_records_external_cortex_provider():
    payload = {
        "executive_summary": "API service.",
        "capability_decomposition": [],
        "refactor_plan": [],
        "cognitive_loop": "call /health",
        "open_questions": [],
        "confidence": "high",
    }
    config = LocalInferenceConfig(
        base_url="https://provider.example/v1",
        model="large-cortex",
        provider_label="external_l4",
    )
    with patch("runtime.project_deliberation.call_json_chat", return_value=payload):
        result = deliberate_project_report(_report(), level35_signals={"signals": []}, config=config)

    assert result["source"] == "external_l4"
    assert result["model"] == "large-cortex"
    assert result["context_mode"] == "expanded"


def test_project_deliberation_normalizes_contract_types():
    payload = {
        "executive_summary": ["API service."],
        "capability_decomposition": "health check",
        "refactor_plan": ["split handlers", "pin deps", "add tests", "extra"],
        "cognitive_loop": ["call /health", "capture failure"],
        "open_questions": None,
        "confidence": "certain",
    }
    config = LocalInferenceConfig(
        base_url="http://127.0.0.1:8000/v1",
        model="gpt-4.1",
        provider_label="external_l4",
    )
    with patch("runtime.project_deliberation.call_json_chat", return_value=payload):
        result = deliberate_project_report(_report(), level35_signals={"signals": []}, config=config)

    assert result["executive_summary"] == "Expose an API"
    assert result["capability_decomposition"] == ["app/api/server.py:handle_chat"]
    assert result["refactor_plan"] == [
        "Define first pipeline capability contract for app/api/server.py:handle_chat",
        "Wrap process boundary app/api/server.py:handle_chat with timeout and captured artifacts",
        "Add idempotency/replay guard around app/api/server.py:handle_chat",
    ]
    assert result["cognitive_loop"] == "call /health"
    assert result["open_questions"]
    assert result["confidence"] == "medium"


def test_project_deliberation_refuses_local_cortex_model():
    with patch("runtime.project_deliberation.call_json_chat") as mocked:
        result = deliberate_project_report(
            _report(),
            level35_signals={"signals": []},
            config=LocalInferenceConfig(base_url="http://127.0.0.1:8000/v1", model="local", provider_label="external_l4"),
        )

    mocked.assert_not_called()
    assert result["source"] == "deterministic_fallback"
    assert result["fallback_reason"] == "external Level 4 cortex provider is required"


def test_project_deliberation_fallback_uses_domain_profile_and_runtime_extraction():
    report = _report()
    project_map = report["execution"]["outputs"]["project_map_report"]
    project_map["summary"]["frameworks"] = []
    project_map["answers"]["1_scope"]["domain_profile"] = {
        "kind": "llm_auto_repair_loop",
        "confidence": 0.98,
    }
    project_map["answers"]["1_scope"]["main_task"] = (
        "Run an LLM-assisted auto-repair loop: copy a template workspace, build/run it in Docker, "
        "send failures to an LLM, apply proposed file updates, and retry."
    )
    project_map["answers"]["6_runtime_extraction_readiness"]["minimal_extraction_plan"] = {
        "capabilities_to_extract": [
            {"capability": "auto_dev_agent.py:send_to_model"},
            {"capability": "auto_dev_agent.py:docker_build"},
            {"capability": "auto_dev_agent.py:docker_run"},
        ]
    }
    signals = {
        "signals": [
            {"type": "MVP_EXTRACTION_CANDIDATE", "target": "auto_dev_agent.py:send_to_model"},
            {"type": "PROCESS_BOUNDARY_CANDIDATE", "target": "auto_dev_agent.py:docker_build"},
        ]
    }

    result = deliberate_project_report(report, level35_signals=signals)

    assert result["source"] == "deterministic_fallback"
    assert result["executive_summary"].startswith("Run an LLM-assisted auto-repair loop")
    assert "unknown stack" not in result["executive_summary"]
    assert result["capability_decomposition"] == [
        "auto_dev_agent.py:send_to_model",
        "auto_dev_agent.py:docker_build",
    ]


def test_architecture_knowledge_uses_domain_profile_over_generic_workflow_terms():
    result = match_architecture_rule(
        {
            "root": "F:/ubuntu/AutoFix&AutoMake/v24",
            "task": "Run workflow tasks around generated modules and Docker repair attempts.",
            "domain_profile": {"kind": "llm_auto_repair_loop", "confidence": 0.98},
            "central": ["autofix_docker/goal_to_spec.py:goal_to_spec"],
            "capabilities": ["autofix_docker/module_contract_checker.py:check_single_module_output"],
        },
        load_architecture_knowledge(),
    )

    assert result["rule"]["rule_id"] == "llm_auto_repair_loop"
    assert any("domain profile" in reason for reason in result["matched_because"])


def test_project_facts_preserve_repair_domain_anchors():
    report = {
        "execution": {
            "outputs": {
                "project_map_report": {
                    "answers": {
                        "1_scope": {"domain_profile": {"kind": "llm_auto_repair_loop"}},
                        "2_execution": {},
                        "3_capabilities": {},
                        "4_contracts_data": {},
                        "5_errors_state_repro": {},
                        "6_runtime_extraction_readiness": {},
                    },
                    "summary": {"root": "F:/ubuntu/AutoFix&AutoMake/v24"},
                },
                "extract_python_structure": {
                    "files": [
                        {
                            "path": "AutoFix/auto_dev_agent.py",
                            "functions": [
                                {"name": "docker_run", "loc": 12},
                                {"name": "send_to_model", "loc": 35},
                            ],
                        },
                        {
                            "path": "autofix_docker/generated_v2/pipeline.py",
                            "functions": [{"name": "send_to_model", "loc": 20}],
                        },
                    ]
                },
            }
        }
    }

    digest = llm_fact_digest(facts_from_project_report(report))

    assert digest["domain_anchors"][0] == "AutoFix/auto_dev_agent.py:send_to_model"
    assert all("generated_v2" not in item for item in digest["domain_anchors"])


def test_project_deliberation_humanizes_refactor_impulses():
    report = _report()
    signals = {
        "signals": [
            {
                "type": "WEAK_CONTRACT",
                "target": "app/api/server.py:handle_chat",
                "suggested_action": "inspect_weak_contract",
            },
            {
                "type": "BROAD_FUNCTION",
                "target": "app/api/server.py:handle_chat",
                "suggested_action": "split_mixed_responsibilities",
            },
        ]
    }

    result = deliberate_project_report(report, level35_signals=signals)

    assert result["refactor_plan"] == [
        "Split mixed responsibilities in app/api/server.py:handle_chat",
        "Define explicit input/output contract for app/api/server.py:handle_chat",
    ]


def test_project_deliberation_prioritizes_runtime_refactor_risks():
    report = _report()
    project_map = report["execution"]["outputs"]["project_map_report"]
    project_map["answers"]["6_runtime_extraction_readiness"]["idempotency_risks"] = [
        {"target": "auto_dev_agent.py:write_files"}
    ]
    project_map["answers"]["6_runtime_extraction_readiness"]["process_boundary_candidates"] = [
        {"target": "auto_dev_agent.py:docker_run"}
    ]
    project_map["answers"]["6_runtime_extraction_readiness"]["minimal_extraction_plan"] = {
        "capabilities_to_extract": [{"capability": "auto_dev_agent.py:send_to_model"}]
    }
    signals = {
        "signals": [
            {
                "type": "WEAK_CONTRACT",
                "target": "auto_dev_agent.py:__init__",
                "suggested_action": "inspect_weak_contract",
            },
            {
                "type": "IDEMPOTENCY_RISK",
                "target": "auto_dev_agent.py:write_files",
                "suggested_action": "add_idempotency_or_replay_guard",
            },
            {
                "type": "PROCESS_BOUNDARY_CANDIDATE",
                "target": "auto_dev_agent.py:docker_run",
                "suggested_action": "prefer_process_boundary",
            },
            {
                "type": "MVP_EXTRACTION_CANDIDATE",
                "target": "auto_dev_agent.py:send_to_model",
                "suggested_action": "draft_first_pipeline_capability",
            },
        ]
    }

    result = deliberate_project_report(report, level35_signals=signals)

    assert result["refactor_plan"] == [
        "Define first pipeline capability contract for auto_dev_agent.py:send_to_model",
        "Wrap process boundary auto_dev_agent.py:docker_run with timeout and captured artifacts",
        "Add idempotency/replay guard around auto_dev_agent.py:write_files",
    ]
