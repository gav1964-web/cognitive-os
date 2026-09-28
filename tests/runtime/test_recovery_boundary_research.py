from runtime.contract_registry import ContractRegistry
from runtime.recovery_boundary_research import build_recovery_boundary_research


def test_boundary_research_blocks_developer_until_architect_evidence() -> None:
    audit = {
        "report_path": "audit.json",
        "clusters": [
            {
                "cluster": "request_mapping_inside_network_boundary",
                "recipe_priority": "high",
                "recipe_status": "missing",
                "automatic_recipe_eligible": False,
                "independent_project_count": 3,
                "unique_structural_shape_count": 7,
                "unresolved_samples": ["one.py:send", "two.py:send"],
            },
            {
                "cluster": "parse_text_inside_io_boundary",
                "recipe_priority": "high",
                "recipe_status": "implemented",
                "automatic_recipe_eligible": True,
            },
        ],
    }

    report = build_recovery_boundary_research(audit)

    assert report["status"] == "architect_review_required"
    assert len(report["hypotheses"]) == 1
    hypothesis = report["hypotheses"][0]
    assert hypothesis["boundary_contract"]["pure_candidate"] == "build_request_payload"
    assert hypothesis["developer_request"] is None
    assert report["architect_gate"]["automatic_admission"] is False
    assert report["architect_gate"]["developer_handoff_allowed"] is False
    assert report["safety"]["source_changes"] is False
    ContractRegistry({}).validate_artifact(report)
