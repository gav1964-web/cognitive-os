from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from runtime.llm_graph_planner import plan_pipeline_with_llm
from runtime.registry import CapabilityRegistry


def test_llm_graph_planner_validates_model_plan():
    root = Path(__file__).resolve().parents[2]
    registry = CapabilityRegistry(root)
    registry.reset_from_plugins()
    proposal = {
        "id": "llm_normalize_hash",
        "version": "0.1.0",
        "steps": [
            {"id": "normalize", "capability": "normalize_text", "input": {"text": "$input.text"}},
            {"id": "hash", "capability": "hash_payload", "input": {"value": "$nodes.normalize.output.text"}},
        ],
        "retry_policy": {"max_attempts": 1, "retry_on": ["transient"]},
    }

    with patch("runtime.llm_graph_planner.call_json_chat", return_value=proposal):
        result = plan_pipeline_with_llm("normalize text then hash it", registry)

    assert result["status"] == "planned"
    assert result["pipeline"]["id"] == "llm_normalize_hash"
    assert result["pipeline"]["edges"] == [["normalize", "hash"]]
    assert result["selection"][0]["capability_id"] == "normalize_text"


def test_llm_graph_planner_includes_memory_hint_in_prompt():
    root = Path(__file__).resolve().parents[2]
    registry = CapabilityRegistry(root)
    registry.reset_from_plugins()
    proposal = {
        "id": "llm_normalize_hash",
        "version": "0.1.0",
        "steps": [
            {"id": "normalize", "capability": "normalize_text", "input": {"text": "$input.text"}},
            {"id": "hash", "capability": "hash_payload", "input": {"value": "$nodes.normalize.output.text"}},
        ],
        "retry_policy": {"max_attempts": 1, "retry_on": ["transient"]},
    }
    memory_hint = {
        "action": "CONSIDER_REUSE_PREVIOUS_PLAN",
        "pipeline_id": "normalize_and_hash",
        "capabilities": ["normalize_text", "hash_payload"],
    }

    with patch("runtime.llm_graph_planner.call_json_chat", return_value=proposal) as call:
        plan_pipeline_with_llm("normalize text then hash it", registry, memory_hint=memory_hint)

    messages = call.call_args.args[0]
    assert "CONSIDER_REUSE_PREVIOUS_PLAN" in messages[1]["content"]
    assert "normalize_and_hash" in messages[1]["content"]
