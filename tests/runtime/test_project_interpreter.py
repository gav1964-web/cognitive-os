from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from runtime.project_deliberation import deliberate_project_report
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
