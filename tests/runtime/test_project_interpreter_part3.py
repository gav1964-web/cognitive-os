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

def test_architecture_synthesis_names_multi_agent_orchestration_slice():
    report = _report()
    project_map = report["execution"]["outputs"]["project_map_report"]
    project_map["summary"] = {
        "root": "F:/ubuntu/VAAT-v4/vaat-v4_20250828",
        "frameworks": ["FastAPI"],
        "routes": 17,
        "entrypoints": ["api/main.py", "run_api.py", "start_agent.py"],
    }
    project_map["answers"]["1_scope"]["main_task"] = (
        "VAAT v4 - Virtual AI-agent Team with A2A protocol, orchestrator, agent groups, and consensus engine."
    )
    project_map["answers"]["1_scope"]["domain_profile"] = {
        "kind": "multi_agent_orchestration_runtime",
        "confidence": 0.95,
        "evidence": ["A2A protocol", "consensus engine", "orchestrator evidence", "agent group management evidence"],
    }
    project_map["answers"]["2_execution"]["central_flow_nodes"] = [
        {"path": "core/orchestrator/orchestrator.py", "name": "_execute_group", "call_count": 12, "loc": 90},
        {"path": "core/consensus/engine.py", "name": "run_consensus", "call_count": 10, "loc": 134},
        {"path": "core/a2a_protocol/protocol.py", "name": "create_task", "call_count": 7, "loc": 40},
    ]
    project_map["answers"]["3_capabilities"]["too_broad_functions"] = [
        {"path": "core/orchestrator/orchestrator.py", "name": "_execute_group", "loc": 90},
        {"path": "core/consensus/engine.py", "name": "run_consensus", "loc": 134},
    ]
    project_map["answers"]["6_runtime_extraction_readiness"]["hidden_orchestrators"] = [
        {"path": "core/orchestrator/orchestrator.py", "name": "_execute_group", "loc": 90, "call_count": 12}
    ]
    project_map["answers"]["6_runtime_extraction_readiness"]["process_boundary_candidates"] = [
        {"target": "core/consensus/engine.py:run_consensus", "reasons": ["network_timeout"]}
    ]
    project_map["answers"]["6_runtime_extraction_readiness"]["minimal_extraction_plan"] = {
        "capabilities_to_extract": [
            {"capability": "core/consensus/engine.py:run_consensus"},
            {"capability": "core/orchestrator/orchestrator.py:_execute_group"},
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

    assert result["project_profile"]["archetype"] == "multi_agent_orchestration_runtime"
    assert result["knowledge"]["matched_rule"] == "multi_agent_orchestration_runtime"
    assert result["recommended_first_slice"]["name"] == "agent_consensus_orchestration_slice"
    assert result["recommended_first_slice"]["knowledge_rule"] == "multi_agent_orchestration_runtime"
    assert any("ConsensusResult" in step for step in result["recommended_first_slice"]["steps"])


def test_architecture_synthesis_names_ml_competition_inference_slice():
    report = _report()
    project_map = report["execution"]["outputs"]["project_map_report"]
    project_map["summary"] = {
        "root": "F:/ubuntu/zindi.africa.vscode",
        "frameworks": [],
        "routes": 0,
        "entrypoints": [],
    }
    project_map["answers"]["1_scope"]["main_task"] = (
        "Run an ML competition inference workflow from prompts.csv to local_submission.csv with transformers."
    )
    project_map["answers"]["1_scope"]["inputs"] = ["prompt/test CSV rows", "model/tokenizer configuration"]
    project_map["answers"]["1_scope"]["outputs"] = ["submission CSV rows", "generated answer text"]
    project_map["answers"]["1_scope"]["domain_profile"] = {
        "kind": "ml_competition_inference_script",
        "confidence": 0.95,
        "evidence": ["ML/model inference imports", "competition-style prompt/submission files", "local transformer generation path"],
    }
    project_map["answers"]["2_execution"]["central_flow_nodes"] = [
        {"path": "x31.py", "name": "generate_response", "call_count": 4, "loc": 8},
        {"path": "x31.py", "name": "postprocess", "call_count": 2, "loc": 5},
    ]
    project_map["answers"]["3_capabilities"]["atomic_reusable_capabilities"] = [
        "x31.py:generate_response",
        "x31.py:postprocess",
    ]
    project_map["answers"]["3_capabilities"]["pure_transforms"] = [
        {"path": "x31.py", "name": "postprocess", "loc": 5},
    ]
    project_map["answers"]["6_runtime_extraction_readiness"]["process_boundary_candidates"] = [
        {"target": "x31.py:generate_response", "reasons": ["large_model_runtime"]}
    ]
    project_map["answers"]["6_runtime_extraction_readiness"]["minimal_extraction_plan"] = {
        "capabilities_to_extract": [
            {"capability": "x31.py:generate_response"},
            {"capability": "x31.py:postprocess"},
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

    assert result["project_profile"]["archetype"] == "ml_competition_inference_script"
    assert result["knowledge"]["matched_rule"] == "ml_competition_inference_script"
    assert result["recommended_first_slice"]["name"] == "ml_inference_submission_slice"
    assert any("PromptRow" in step for step in result["recommended_first_slice"]["steps"])


def test_architecture_synthesis_names_map_viewport_slice():
    report = _report()
    project_map = report["execution"]["outputs"]["project_map_report"]
    project_map["summary"] = {
        "root": "F:/ubuntu/test/map",
        "frameworks": ["Flask-like Python web app"],
        "routes": 20,
        "entrypoints": ["RUN_MAP.bat", "app.py"],
    }
    project_map["answers"]["1_scope"]["main_task"] = "Offline map package with incidents and bbox filtering."
    project_map["answers"]["1_scope"]["inputs"] = ["HTTP requests", "files or structured documents"]
    project_map["answers"]["1_scope"]["outputs"] = ["HTTP/API responses", "database state"]
    project_map["answers"]["3_capabilities"]["pure_transforms"] = [
        {"path": "app.py", "name": "parse_bbox"},
        {"path": "app.py", "name": "point_in_bbox"},
    ]
    project_map["answers"]["3_capabilities"]["too_broad_functions"] = [
        {"path": "app.py", "name": "index", "loc": 1144},
    ]
    project_map["answers"]["6_runtime_extraction_readiness"]["minimal_extraction_plan"] = [
        {"capability": "app.py:parse_bbox"},
        {"capability": "app.py:point_in_bbox"},
        {"capability": "app.py:set_incident_data"},
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

    assert result["project_profile"]["knowledge_rule"] == "web_gis_data_application"
    assert result["project_profile"]["archetype"] == "web_gis_data_application"
    assert result["knowledge"]["matched_rule"] == "web_gis_data_application"
    assert result["recommended_first_slice"]["name"] == "map_viewport_query_slice"
    assert "app.py:parse_bbox" in result["recommended_first_slice"]["targets"]
    assert any("bbox" in step.lower() for step in result["recommended_first_slice"]["steps"])


def test_architecture_synthesis_demotes_generated_version_targets():
    report = _report()
    project_map = report["execution"]["outputs"]["project_map_report"]
    project_map["summary"] = {
        "root": "F:/ubuntu/AutoFix&AutoMake/v24",
        "frameworks": ["Python"],
        "routes": 0,
        "entrypoints": ["AutoFix/main.py", "autofix_docker/run_all_autofix.py"],
    }
    project_map["answers"]["1_scope"]["main_task"] = (
        "Run an LLM-assisted auto-repair loop with Docker verification and generated module outputs."
    )
    project_map["answers"]["3_capabilities"]["too_broad_functions"] = [
        {"path": "autofix_docker/generated_v2/pipeline.py", "name": "extract_reviews_from_page", "loc": 79},
        {"path": "autofix_docker/goal_to_spec.py", "name": "goal_to_spec", "loc": 90},
    ]
    project_map["answers"]["6_runtime_extraction_readiness"]["minimal_extraction_plan"] = {
        "capabilities_to_extract": [
            {"capability": "autofix_docker/generated_v2/pipeline.py:extract_reviews_from_page"},
            {"capability": "autofix_docker/goal_to_spec.py:goal_to_spec"},
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

    targets = result["recommended_first_slice"]["targets"]
    assert targets
    assert not targets[0].startswith("autofix_docker/generated_v2/")


@pytest.mark.parametrize(
    ("rule_id", "facts"),
    [
        (
            "llm_gateway_service",
            {
                "root": "llm-gateway",
                "frameworks": ["FastAPI"],
                "central": ["chat_completions", "select_provider", "build_key"],
                "capabilities": ["provider_url", "cache key"],
            },
        ),
        (
            "web_gis_data_application",
            {
                "root": "map-viewer",
                "frameworks": ["Flask-like Python web app"],
                "central": ["parse_bbox", "point_in_bbox"],
                "capabilities": ["incident filtering", "GeoJSON viewport"],
                "routes_count": 20,
            },
        ),
    ],
)
def test_architecture_knowledge_matches_new_pattern_records(rule_id, facts):
    knowledge = load_architecture_knowledge()

    result = match_architecture_rule(facts, knowledge)

    assert result["rule"]["rule_id"] == rule_id


@pytest.mark.parametrize(
    ("rule_id", "facts"),
    [
        (
            "web_gis_data_application",
            {
                "root": "map-context-copy",
                "frameworks": ["Flask-like Python web app"],
                "central": ["parse_bbox", "point_in_bbox"],
                "capabilities": ["incident filtering", "GeoJSON viewport"],
                "domain_profile": {"kind": "web_gis_data_application"},
                "routes_count": 20,
            },
        ),
    ],
)
def test_architecture_knowledge_prefers_project_archetype_over_incidental_internal_terms(rule_id, facts):
    result = match_architecture_rule(facts, load_architecture_knowledge())

    assert result["rule"]["rule_id"] == rule_id


def test_interpret_project_report_cli_writes_output(tmp_path):
    root = Path(__file__).resolve().parents[2]
    report_path = tmp_path / "report.json"
    output_path = tmp_path / "interpretation.json"
    report_path.write_text(json.dumps(_report()), encoding="utf-8")
    script = (
        "import json\n"
        "from unittest.mock import patch\n"
        "from tools.interpret_project_report import main\n"
        "signals = {'signals': [], 'confidence': 'high', 'source': 'local_llm', 'layer': 'L3.5'}\n"
        "interpretation = {\n"
        " 'executive_summary': 'API service.',\n"
        " 'capability_decomposition': ['health check'],\n"
        " 'refactor_plan': ['split handlers'],\n"
        " 'cognitive_loop': ['call /health'],\n"
        " 'open_questions': [],\n"
        " 'confidence': 'high',\n"
        " 'source': 'local_llm',\n"
        " 'layer': 'L4',\n"
        "}\n"
        "with patch('runtime.project_interpreter.generate_project_signals', return_value=signals), patch('runtime.project_interpreter.deliberate_project_report', return_value=interpretation):\n"
        f" import sys; sys.argv = ['tool', '--root', r'{root}', '--report', r'{report_path}', '--output', r'{output_path}']; raise SystemExit(main())\n"
    )
    completed = subprocess.run([sys.executable, "-c", script], text=True, capture_output=True, check=True)

    assert json.loads(completed.stdout)["status"] == "ok"
    saved = json.loads(output_path.read_text(encoding="utf-8"))
    assert saved["level35_project_signals"]["layer"] == "L3.5"
    assert saved["level4_project_interpretation"]["confidence"] == "high"
    assert saved["analysis_tasks"]["task_count"] >= 0
    assert saved["architecture_synthesis"]["artifact_type"] == "ProjectArchitectureSynthesis"
