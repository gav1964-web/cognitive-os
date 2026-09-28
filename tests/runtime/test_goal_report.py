from __future__ import annotations

from runtime.goal_report import build_goal_report


def test_goal_report_preserves_llm_interpretation():
    session = {"goal_id": "goal_test", "goal": "Analyze project", "events": []}
    payload = {
        "status": "decided",
        "goal_intake": {"artifact_type": "GoalSpec", "status": "ready", "intent": "analyze_project"},
        "level4_decision": {"action": "PLAN_WITH_L35"},
        "layer_packets": [{"packet_type": "INTENT", "correlation_id": "goal_test"}],
        "level35_plan": {"status": "planned"},
        "execution": {"status": "ok", "completed_nodes": ["project_map_report"]},
        "level35_project_signals": {
            "source": "local_llm",
            "layer": "L3.5",
            "signals": [{"type": "ENTRYPOINT_FOUND", "target": "app.py"}],
        },
        "level4_project_interpretation": {
            "source": "local_llm",
            "layer": "L4",
            "executive_summary": "FastAPI service.",
            "confidence": "high",
        },
        "analysis_tasks": {
            "source": "deterministic_task_synthesizer",
            "task_count": 1,
            "tasks": [{"type": "EXTRACT_CAPABILITY", "target": "app.py:index"}],
        },
        "architecture_synthesis": {
            "artifact_type": "ProjectArchitectureSynthesis",
            "source": "deterministic_architecture_synthesis",
            "recommended_first_slice": {"name": "first_bounded_capability_slice"},
        },
    }

    report = build_goal_report(session, payload)

    assert report["goal_intake"]["intent"] == "analyze_project"
    assert report["level35_project_signals"]["layer"] == "L3.5"
    assert report["level4_project_interpretation"]["layer"] == "L4"
    assert report["level4_project_interpretation"]["confidence"] == "high"
    assert report["analysis_tasks"]["task_count"] == 1
    assert report["architecture_synthesis"]["artifact_type"] == "ProjectArchitectureSynthesis"
    assert report["layer_packets"][0]["packet_type"] == "INTENT"
