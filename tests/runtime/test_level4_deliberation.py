from pathlib import Path

from runtime.goal_orchestrator import decide_goal_route
from runtime.level4_deliberation import build_deliberation
from runtime.registry import CapabilityRegistry


def test_level4_deliberation_records_route_risks_and_recommendation():
    root = Path(__file__).resolve().parents[2]
    registry = CapabilityRegistry(root)
    registry.reset_from_plugins()
    decision = decide_goal_route("Parse a PDF file from $input.path", registry)

    deliberation = build_deliberation(
        goal="Parse a PDF file from $input.path",
        decision=decision,
        registry=registry,
        memory_preflight={"matches": [], "template_matches": []},
    )

    assert deliberation["route"] == "L4 -> L3.5 -> L2"
    assert deliberation["recommendation"] == "continue_to_level35"
    assert deliberation["capabilities"][0]["id"] == "parse_pdf"
    assert deliberation["selected_alternative"]["id"] == "deterministic_required_capabilities"
    assert any(risk["code"] == "no_mature_memory_template" for risk in deliberation["risks"])


def test_level4_deliberation_prefers_mature_memory_template():
    root = Path(__file__).resolve().parents[2]
    registry = CapabilityRegistry(root)
    registry.reset_from_plugins()
    decision = decide_goal_route("Parse a PDF file from $input.path", registry)

    deliberation = build_deliberation(
        goal="Parse a PDF file from $input.path",
        decision=decision,
        registry=registry,
        memory_preflight={
            "matches": [],
            "template_matches": [],
            "template_recommendation": {
                "template_id": "tpl_pdf",
                "support_count": 4,
                "safety_status": "mature",
                "score": 1.0,
            },
        },
    )

    assert [item["id"] for item in deliberation["route_alternatives"]][:2] == [
        "memory_template",
        "deterministic_required_capabilities",
    ]
    assert deliberation["selected_alternative"]["id"] == "memory_template"
