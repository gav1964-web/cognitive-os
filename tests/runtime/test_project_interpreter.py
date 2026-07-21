from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from runtime.project_deliberation import deliberate_project_report
from runtime.project_architecture_synthesis import load_architecture_knowledge, match_architecture_rule, synthesize_project_architecture
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
    assert result["capability_decomposition"] == ["Entrypoint workflow: app/api/server.py"]
    assert result["refactor_plan"] == [
        "Review hotspot app/api/server.py:handle_chat",
        "Harden weak contract app/api/server.py:health_check",
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
    assert result["project_profile"]["archetype"] == "llm_gateway_service"
    assert result["knowledge"]["matched_rule"] == "llm_gateway_service"
    assert result["recommended_first_slice"]["name"] == "chat_completion_proxy_slice"
    assert any("ProviderDecision" in step for step in result["recommended_first_slice"]["steps"])
    assert result["task_focus"][0]["type"] == "DRAFT_PIPELINE_CAPABILITY"
    assert any(row["pattern_id"] == "build_cache_key" for row in result["matched_capability_patterns"])
    assert any(row["risk_id"] == "live_provider_test" for row in result["matched_risk_patterns"])
    assert any(row["lesson_id"] == "llm_gateway_cache_key_first" for row in result["relevant_lessons"])


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

    assert result["project_profile"]["archetype"] == "web_gis_data_application"
    assert result["knowledge"]["matched_rule"] == "web_gis_data_application"
    assert result["recommended_first_slice"]["name"] == "map_viewport_query_slice"
    assert "app.py:parse_bbox" in result["recommended_first_slice"]["targets"]
    assert any("bbox" in step.lower() for step in result["recommended_first_slice"]["steps"])


@pytest.mark.parametrize(
    ("rule_id", "facts"),
    [
        (
            "asgi_wsgi_server_runtime",
            {
                "root": "uvicorn",
                "central": ["server.py:serve", "protocol.py:lifespan", "workers.py:graceful_shutdown"],
                "capabilities": ["protocol.py:run_wsgi"],
                "task": "ASGI server socket lifecycle and graceful shutdown runtime",
            },
        ),
        (
            "template_rendering_engine",
            {
                "central": ["environment.py:render", "loader.py:get_template"],
                "capabilities": ["nodes.py:parse", "escape.py:escape"],
                "task": "Jinja template context rendering engine",
            },
        ),
        (
            "auth_security_library",
            {
                "root": "authlib",
                "central": ["auth.py:authenticate", "permissions.py:authorize"],
                "capabilities": ["tokens.py:validate_token", "csrf.py:check_csrf"],
                "task": "OAuth JWT permission and session cookie validation",
            },
        ),
        (
            "observability_metrics_tracing",
            {
                "central": ["metrics.py:record", "trace.py:start_span"],
                "capabilities": ["exporter.py:export", "telemetry.py:emit"],
                "task": "OpenTelemetry Prometheus metrics trace span exporter",
            },
        ),
        (
            "scientific_compute_library",
            {
                "root": "numpy",
                "central": ["solver.py:solve", "array.py:compute"],
                "capabilities": ["fft.py:transform", "matrix.py:fit"],
                "task": "NumPy SciPy ndarray tensor matrix solver",
            },
        ),
        (
            "protocol_api_client",
            {
                "central": ["client.py:request_builder", "transport.py:send"],
                "capabilities": ["response.py:parse_response", "retry.py:retry"],
                "task": "API client transport retry rate limit response parser",
            },
        ),
        (
            "signing_token_utility",
            {
                "root": "itsdangerous",
                "central": ["serializer.py:dumps", "serializer.py:loads"],
                "capabilities": ["signer.py:sign", "signer.py:unsign"],
                "task": "itsdangerous signer serializer token signature verification utility",
            },
        ),
        (
            "async_protocol_runtime",
            {
                "root": "websockets",
                "central": ["protocol.py:handshake", "connection.py:handle"],
                "capabilities": ["lifespan.py:run"],
                "task": "WebSockets async protocol runtime with cancellation and handshake",
            },
        ),
        (
            "schema_validation_library",
            {
                "root": "cerberus",
                "central": ["validator.py:validate", "schema.py:check"],
                "capabilities": ["errors.py:format"],
                "task": "Cerberus data validation schema validator",
            },
        ),
        (
            "workflow_orchestrator",
            {
                "root": "airflow",
                "central": ["trigger_dag.py:_trigger_dag", "scheduler_job.py:run"],
                "capabilities": ["taskinstance.py:run"],
                "task": "Airflow DAG workflow scheduler task trigger worker runtime",
            },
        ),
        (
            "automation_engine",
            {
                "root": "ansible",
                "central": ["playbook_executor.py:run", "task_executor.py:run"],
                "capabilities": ["module_common.py:modify_module"],
                "task": "Ansible playbook inventory task module yaml templating connection execution",
            },
        ),
        (
            "backup_archive_tool",
            {
                "root": "borg",
                "central": ["archive.py:rebuild_archives", "repository.py:commit"],
                "capabilities": ["chunker.py:chunkify"],
                "task": "Borg backup archive repository restore chunk manifest dedup tool",
            },
        ),
        (
            "packaging_freezer",
            {
                "root": "pyinstaller",
                "central": ["build_main.py:build", "Scripting.py:waf_entry_point"],
                "capabilities": ["depend/analysis.py:analyze"],
                "task": "PyInstaller bootloader hook spec freeze bundle analysis packaging",
            },
        ),
        (
            "proxy_security_tool",
            {
                "root": "mitmproxy",
                "central": ["proxy/server.py:serve", "certs.py:create_ca"],
                "capabilities": ["flow.py:copy"],
                "task": "mitmproxy proxy tls certificate flow http websocket intercept security tool",
            },
        ),
        (
            "desktop_gui_ide",
            {
                "root": "spyder",
                "central": ["plugins/editor/plugin.py:on_initialize"],
                "capabilities": ["pylsp/plugins/symbols.py:pylsp_document_symbols"],
                "task": "Spyder Qt widget plugin editor LSP workspace preferences desktop IDE",
            },
        ),
        (
            "ml_app_framework",
            {
                "root": "gradio",
                "central": ["blocks.py:launch", "routes.py:mount_gradio_app"],
                "capabilities": ["components/base.py:process_example"],
                "task": "Gradio component blocks interface dataset queue frontend FastAPI ML app framework",
            },
        ),
        (
            "distributed_compute_graph",
            {
                "root": "dask",
                "central": ["array/blockwise.py:blockwise", "base.py:compute"],
                "capabilities": ["highlevelgraph.py:from_collections"],
                "task": "Dask graph task scheduler array dataframe partition blockwise distributed compute",
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
            "http_client_library",
            {
                "root": "httpx",
                "central": ["httpx/_client.py:send"],
                "capabilities": ["httpx/_decoders.py:flush"],
                "task": "HTTPX is a fully featured HTTP client library for Python.",
            },
        ),
        (
            "web_framework_library",
            {
                "root": "django",
                "central": ["django/core/handlers/base.py:get_response"],
                "capabilities": ["django/core/cache/backends/base.py:memcache_key_warnings"],
                "task": "Django web framework and request handling runtime.",
            },
        ),
        (
            "web_framework_library",
            {
                "root": "starlette",
                "central": ["starlette/routing.py:handle"],
                "capabilities": ["starlette/_utils.py:is_async_callable"],
                "task": "Starlette web framework routing and middleware.",
            },
        ),
        (
            "workflow_orchestrator",
            {
                "root": "prefect",
                "central": ["server/api/flows.py:create_flow", "workers/base.py:run"],
                "capabilities": ["task_engine.py:run_task"],
                "frameworks": ["FastAPI"],
                "task": "Prefect FastAPI flow task scheduler worker orchestration runtime.",
            },
        ),
        (
            "ml_app_framework",
            {
                "root": "gradio",
                "central": ["routes.py:create_app"],
                "capabilities": ["blocks.py:process_api"],
                "frameworks": ["FastAPI"],
                "task": "Gradio FastAPI component blocks interface queue frontend framework.",
            },
        ),
        (
            "packaging_build_backend",
            {
                "root": "poetry",
                "central": ["src/poetry/factory.py:create_pool"],
                "capabilities": ["src/poetry/factory.py:create_pool"],
                "task": "Python packaging and project metadata management tool.",
            },
        ),
        (
            "visualization_plotting_library",
            {
                "root": "matplotlib",
                "central": ["lib/matplotlib/figure.py:savefig"],
                "capabilities": ["lib/matplotlib/__init__.py:set_loglevel"],
                "task": "Matplotlib visualization plotting library.",
            },
        ),
        (
            "scientific_compute_library",
            {
                "root": "numpy",
                "central": ["numpy/_core/_multiarray_umath.py:array"],
                "capabilities": ["numpy/_array_api_info.py:capabilities"],
                "task": "NumPy numerical array compute library.",
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
