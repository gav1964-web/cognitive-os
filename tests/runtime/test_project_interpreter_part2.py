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

def test_project_deliberation_prefers_distinct_refactor_targets():
    report = _report()
    signals = {
        "signals": [
            {"type": "MVP_EXTRACTION_CANDIDATE", "target": "auto_dev_agent.py:copy_template", "suggested_action": "draft_first_pipeline_capability"},
            {"type": "MVP_EXTRACTION_CANDIDATE", "target": "auto_dev_agent.py:docker_build", "suggested_action": "draft_first_pipeline_capability"},
            {"type": "MVP_EXTRACTION_CANDIDATE", "target": "auto_dev_agent.py:send_to_model", "suggested_action": "draft_first_pipeline_capability"},
            {"type": "PROCESS_BOUNDARY_CANDIDATE", "target": "auto_dev_agent.py:clean_docker_if_needed", "suggested_action": "prefer_process_boundary"},
            {"type": "PROCESS_BOUNDARY_CANDIDATE", "target": "auto_dev_agent.py:docker_build", "suggested_action": "prefer_process_boundary"},
            {"type": "PROCESS_BOUNDARY_CANDIDATE", "target": "auto_dev_agent.py:docker_run", "suggested_action": "prefer_process_boundary"},
            {"type": "IDEMPOTENCY_RISK", "target": "auto_dev_agent.py:copy_template", "suggested_action": "add_idempotency_or_replay_guard"},
            {"type": "IDEMPOTENCY_RISK", "target": "auto_dev_agent.py:docker_build", "suggested_action": "add_idempotency_or_replay_guard"},
            {"type": "IDEMPOTENCY_RISK", "target": "auto_dev_agent.py:docker_run", "suggested_action": "add_idempotency_or_replay_guard"},
        ]
    }
    readiness = report["execution"]["outputs"]["project_map_report"]["answers"]["6_runtime_extraction_readiness"]
    readiness["minimal_extraction_plan"] = {
        "capabilities_to_extract": [
            {"capability": "auto_dev_agent.py:send_to_model"},
            {"capability": "auto_dev_agent.py:copy_template"},
        ]
    }
    readiness["process_boundary_candidates"] = [
        {"target": "auto_dev_agent.py:docker_build"},
        {"target": "auto_dev_agent.py:docker_run"},
    ]
    readiness["idempotency_risks"] = [
        {"target": "auto_dev_agent.py:copy_template"},
        {"target": "auto_dev_agent.py:docker_build"},
        {"target": "auto_dev_agent.py:docker_run"},
    ]

    result = deliberate_project_report(report, level35_signals=signals)

    assert result["refactor_plan"] == [
        "Define first pipeline capability contract for auto_dev_agent.py:send_to_model",
        "Wrap process boundary auto_dev_agent.py:docker_run with timeout and captured artifacts",
        "Add idempotency/replay guard around auto_dev_agent.py:copy_template",
    ]


def test_project_deliberation_allows_external_model_through_local_gateway():
    payload = {
        "executive_summary": "API service.",
        "capability_decomposition": [],
        "refactor_plan": [],
        "cognitive_loop": "call /health",
        "open_questions": [],
        "confidence": "high",
    }
    config = LocalInferenceConfig(
        base_url="http://127.0.0.1:8000/v1",
        model="gpt-4o-mini",
        provider_label="external_l4",
    )
    with patch("runtime.project_deliberation.call_json_chat", return_value=payload) as mocked:
        result = deliberate_project_report(_report(), level35_signals={"signals": []}, config=config)

    mocked.assert_called_once()
    assert result["source"] == "external_l4"
    assert result["model"] == "gpt-4o-mini"


def test_project_deliberation_retries_compact_on_context_overflow():
    payload = {
        "executive_summary": "API service.",
        "capability_decomposition": [],
        "refactor_plan": [],
        "cognitive_loop": "call /health",
        "open_questions": [],
        "confidence": "medium",
    }
    config = LocalInferenceConfig(
        base_url="http://127.0.0.1:8000/v1",
        model="gpt-4o-mini",
        provider_label="external_l4",
    )
    with patch(
        "runtime.project_deliberation.call_json_chat",
        side_effect=[LocalInferenceError("request exceeds the available context size n_ctx=2048"), payload],
    ) as mocked:
        result = deliberate_project_report(_report(), level35_signals={"signals": []}, config=config)

    assert mocked.call_count == 2
    assert result["source"] == "external_l4"
    assert result["context_mode"] == "compact_after_overflow"


def test_project_interpreter_wrapper_returns_layers():
    signals = {"signals": [], "confidence": "high", "source": "local_llm", "layer": "L3.5"}
    interpretation = {"executive_summary": "API service.", "confidence": "high", "source": "local_llm", "layer": "L4"}
    with patch("runtime.project_interpreter.generate_project_signals", return_value=signals), patch(
        "runtime.project_interpreter.deliberate_project_report", return_value=interpretation
    ):
        result = interpret_project_report(_report())

    assert result["level35_project_signals"]["layer"] == "L3.5"
    assert result["level4_project_interpretation"]["layer"] == "L4"
    assert result["analysis_tasks"]["source"] == "deterministic_task_synthesizer"
    assert result["architecture_synthesis"]["source"] == "knowledge_backed_architecture_synthesis"


def test_project_tasks_turn_signals_into_actionable_backlog():
    signals = {
        "signals": [
            {"type": "SUBSYSTEM_HOTSPOT", "target": "app/api", "severity": "high"},
            {"type": "BROAD_FUNCTION", "target": "app/api/server.py:handle_chat", "severity": "high"},
            {"type": "WEAK_CONTRACT", "target": "app/api/server.py:health", "severity": "medium"},
        ]
    }
    interpretation = {
        "refactor_plan": ["Split app/api/server.py:handle_chat into parser and dispatcher"],
        "open_questions": ["Who owns app/providers?"],
    }

    result = generate_project_tasks(level35_signals=signals, level4_interpretation=interpretation)

    task_types = {task["type"] for task in result["tasks"]}
    assert result["layer"] == "L4"
    assert "MAP_SUBSYSTEM_BOUNDARY" in task_types
    assert "EXTRACT_CAPABILITY" in task_types
    assert "HARDEN_CONTRACT" in task_types
    assert any(task["priority"] == "P1" for task in result["tasks"])


def test_project_tasks_include_runtime_safety_backlog():
    signals = {
        "signals": [
            {"type": "MIXED_RESPONSIBILITY", "target": "app/api.py:handle", "severity": "high"},
            {"type": "IDEMPOTENCY_RISK", "target": "app/api.py:save", "severity": "high"},
            {"type": "PROCESS_BOUNDARY_CANDIDATE", "target": "app/worker.py:run", "severity": "medium"},
            {"type": "CHECKPOINT_CANDIDATE", "target": "parsed_intermediate", "severity": "medium"},
            {"type": "MVP_EXTRACTION_CANDIDATE", "target": "app/api.py:normalize", "severity": "high"},
        ]
    }

    result = generate_project_tasks(level35_signals=signals, level4_interpretation={})

    task_types = {task["type"] for task in result["tasks"]}
    assert "SPLIT_MIXED_RESPONSIBILITY" in task_types
    assert "ADD_IDEMPOTENCY_GUARD" in task_types
    assert "ISOLATE_PROCESS_BOUNDARY" in task_types
    assert "DEFINE_CHECKPOINT_POLICY" in task_types
    assert "DRAFT_PIPELINE_CAPABILITY" in task_types


def test_architecture_synthesis_names_gateway_request_slice():
    report = _report()
    execution = report["execution"]["outputs"]["project_map_report"]["answers"]["2_execution"]
    execution["central_flow_nodes"] = [
        {"path": "app/main.py", "name": "chat_completions", "call_count": 14},
        {"path": "app/main.py", "name": "_forward_once", "call_count": 7},
        {"path": "app/main.py", "name": "_normalize_upstream_response", "call_count": 6},
        {"path": "app/main.py", "name": "select_provider", "call_count": 2},
        {"path": "app/cache.py", "name": "build_key", "call_count": 2},
    ]
    report["execution"]["outputs"]["project_map_report"]["answers"]["3_capabilities"]["pure_transforms"] = [
        {"path": "app/main.py", "name": "select_provider"},
        {"path": "app/main.py", "name": "provider_url"},
        {"path": "app/cache.py", "name": "build_key"},
    ]
    report["execution"]["outputs"]["project_map_report"]["answers"]["3_capabilities"]["atomic_reusable_capabilities"] = [
        "app/cache.py:build_key",
        "app/main.py:select_provider",
        "app/main.py:provider_url",
    ]
    signals = generate_project_signals(
        report,
        config=LocalInferenceConfig(base_url="http://127.0.0.1:9/v1", model="disabled", timeout_seconds=0.01),
    )
    interpretation = deliberate_project_report(report, level35_signals=signals)
    tasks = generate_project_tasks(level35_signals=signals, level4_interpretation=interpretation)

    result = synthesize_project_architecture(
        report,
        level35_signals=signals,
        level4_interpretation=interpretation,
        analysis_tasks=tasks,
    )

    assert result["artifact_type"] == "ProjectArchitectureSynthesis"
    assert result["source"] == "knowledge_backed_architecture_synthesis"
    assert result["project_profile"]["knowledge_rule"] == "llm_gateway_service"
    assert result["project_profile"]["archetype"] == "llm_provider_gateway"
    assert result["knowledge"]["matched_rule"] == "llm_gateway_service"
    assert result["recommended_first_slice"]["name"] == "chat_completion_proxy_slice"
    assert any("ProviderDecision" in step for step in result["recommended_first_slice"]["steps"])
    assert result["task_focus"][0]["type"] == "DRAFT_PIPELINE_CAPABILITY"
    assert any(row["pattern_id"] == "build_cache_key" for row in result["matched_capability_patterns"])
    assert any(row["risk_id"] == "live_provider_test" for row in result["matched_risk_patterns"])
    assert any(row["lesson_id"] == "llm_gateway_cache_key_first" for row in result["relevant_lessons"])


def test_architecture_synthesis_prefers_prompt_lab_over_incidental_gateway_terms():
    report = _report()
    project_map = report["execution"]["outputs"]["project_map_report"]
    project_map["summary"] = {
        "root": "D:/wsl/test-0-00-000-001-5--8/002",
        "frameworks": ["FastAPI"],
        "routes": 16,
        "entrypoints": ["prompt_lab.py", "prompt_lab_api.py", "app/main.py"],
    }
    project_map["answers"]["1_scope"]["main_task"] = (
        "Provide a unified OpenAI-compatible gateway for routing chat/completion requests across multiple LLM providers."
    )
    project_map["answers"]["1_scope"]["supported_scenarios"] = ["Accept OpenAI-compatible chat/completion requests."]
    project_map["answers"]["2_execution"]["central_flow_nodes"] = [
        {"path": "prompt_lab.py", "name": "run_validation_once", "call_count": 8, "loc": 44},
        {"path": "prompt_lab.py", "name": "run_auto_loop_once", "call_count": 7, "loc": 91},
        {"path": "prompt_lab_api.py", "name": "create_app", "call_count": 6, "loc": 493},
    ]
    project_map["answers"]["3_capabilities"]["too_broad_functions"] = [
        {"path": "prompt_lab.py", "name": "run_auto_loop_once", "loc": 91},
        {"path": "prompt_lab_api.py", "name": "create_app", "loc": 493},
    ]
    project_map["answers"]["6_runtime_extraction_readiness"]["hidden_orchestrators"] = [
        {"path": "prompt_lab.py", "name": "run_auto_loop_once", "loc": 91, "call_count": 7}
    ]
    project_map["answers"]["6_runtime_extraction_readiness"]["process_boundary_candidates"] = [
        {"target": "prompt_lab.py:run_validation_once", "reasons": ["external_api"]}
    ]
    project_map["answers"]["6_runtime_extraction_readiness"]["minimal_extraction_plan"] = {
        "capabilities_to_extract": [
            {"capability": "prompt_lab.py:run_validation_once"},
            {"capability": "prompt_lab.py:analyze_validation_results"},
            {"capability": "prompt_lab_api.py:create_app"},
        ]
    }

    signals = generate_project_signals(
        report,
        config=LocalInferenceConfig(base_url="http://127.0.0.1:9/v1", model="disabled", timeout_seconds=0.01),
    )
    interpretation = deliberate_project_report(report, level35_signals=signals)
    tasks = generate_project_tasks(level35_signals=signals, level4_interpretation=interpretation)
    result = synthesize_project_architecture(
        report,
        level35_signals=signals,
        level4_interpretation=interpretation,
        analysis_tasks=tasks,
    )

    assert result["project_profile"]["archetype"] == "prompt_lab_evaluation_runtime"
    assert result["knowledge"]["matched_rule"] == "prompt_lab_evaluation_runtime"
    assert result["recommended_first_slice"]["name"] == "prompt_lab_run_artifact_slice"
    assert any("LLMRunResult" in step for step in result["recommended_first_slice"]["steps"])
    assert "prompt laboratory" in result["project_profile"]["purpose_summary"]
