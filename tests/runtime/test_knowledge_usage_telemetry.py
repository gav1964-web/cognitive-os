from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from runtime.knowledge import knowledge_preflight
from runtime.knowledge_usage_telemetry import knowledge_usage_summary, load_knowledge_usage_events
from runtime.project_architecture_synthesis import synthesize_project_architecture


ROOT = Path(__file__).resolve().parents[2]


def test_knowledge_preflight_records_usage_event(tmp_path):
    result = knowledge_preflight(
        "Convert XLS file from $input.input_path to CSV file at $input.output_path",
        {"input_path": "book.xls", "output_path": "out.csv"},
        root=tmp_path,
    )

    events = load_knowledge_usage_events(tmp_path)

    assert result["status"] == "blocked"
    assert events[-1]["artifact_type"] == "KnowledgeUsageEvent"
    assert events[-1]["event_type"] == "kb_preflight_gap"
    assert events[-1]["role"] == "goal_orchestrator"
    assert events[-1]["rule_id"] == "legacy_xls_backend"


def test_architecture_synthesis_records_rule_match_event(tmp_path):
    result = synthesize_project_architecture(
        _project_report(),
        level35_signals={"signals": []},
        level4_interpretation={"confidence": "medium"},
        analysis_tasks={"tasks": []},
        root=tmp_path,
    )

    summary = knowledge_usage_summary(tmp_path)

    assert result["knowledge"]["matched_rule"]
    assert summary["event_count"] == 1
    assert summary["by_event_type"] == {"kb_rule_match": 1}
    assert summary["by_role"] == {"architect": 1}
    assert summary["top_rules"][0][0] == result["knowledge"]["matched_rule"]


def test_knowledge_usage_report_cli_reads_jsonl(tmp_path):
    knowledge_preflight(
        "Convert XLS file from $input.input_path to CSV file at $input.output_path",
        {"input_path": "book.xls", "output_path": "out.csv"},
        root=tmp_path,
    )

    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "knowledge_usage_report.py"), "--root", str(tmp_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["artifact_type"] == "KnowledgeUsageSummary"
    assert payload["event_count"] == 1
    assert payload["by_status"] == {"blocked": 1}


def _project_report() -> dict:
    return {
        "goal_id": "goal_test",
        "execution": {
            "outputs": {
                "project_map_report": {
                    "summary": {"root": "project", "frameworks": ["FastAPI"], "routes": 1},
                    "risks": [],
                    "answers": {
                        "1_scope": {"main_task": "Expose an API"},
                        "2_execution": {
                            "entrypoints": ["app/api/server.py"],
                            "central_flow_nodes": [{"path": "app/api/server.py", "name": "handle_chat", "call_count": 8}],
                        },
                        "3_capabilities": {
                            "pure_transforms": [],
                            "too_broad_functions": [{"path": "app/api/server.py", "name": "handle_chat", "loc": 120}],
                        },
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
                            "hidden_orchestrators": [{"path": "app/api/server.py", "name": "handle_chat", "line": 10, "loc": 120}],
                            "process_boundary_candidates": [{"target": "app/api/server.py:handle_chat"}],
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
