from __future__ import annotations

from runtime.system_knowledge_ir_backlog import build_ir_loss_backlog, load_ir_backlog_policy, summarize_ir_loss_backlog


def test_ir_loss_backlog_policy_loads_categories():
    policy = load_ir_backlog_policy()

    assert policy["categories"]["public_interfaces"]["severity"] == "high"
    assert policy["categories"]["architecture_slices"]["role"] == "architect"


def test_ir_loss_backlog_routes_losses_to_roles():
    diff = {
        "artifact_type": "SystemKnowledgeIRDiff",
        "score": 0.5,
        "losses": [
            {"category": "public_interfaces", "missing": ["route:/health"]},
            {"category": "behavior_contracts", "missing": ["app.py:health"]},
            {"category": "architecture_slices", "missing": ["health_slice"]},
            {"category": "acceptance_tests", "missing": ["AC1"]},
        ],
    }

    backlog = build_ir_loss_backlog(diff)
    roles = {item["category"]: item["role"] for item in backlog}

    assert roles["public_interfaces"] == "project_analyzer"
    assert roles["behavior_contracts"] == "spec_writer"
    assert roles["architecture_slices"] == "architect"
    assert roles["acceptance_tests"] == "spec_writer"
    assert backlog[0]["severity"] == "high"


def test_ir_loss_backlog_summary_counts_roles_and_severity():
    backlog = build_ir_loss_backlog(
        {
            "artifact_type": "SystemKnowledgeIRDiff",
            "score": 0.4,
            "losses": [
                {"category": "public_interfaces", "missing": ["route:/health"]},
                {"category": "behavior_contracts", "missing": ["app.py:health"]},
            ],
        }
    )

    summary = summarize_ir_loss_backlog(backlog)

    assert summary["items"] == 2
    assert summary["by_role"] == {"project_analyzer": 1, "spec_writer": 1}
    assert summary["by_severity"] == {"high": 2}
