from __future__ import annotations

from runtime.system_knowledge_ir_diff import compare_system_knowledge_ir


def test_system_knowledge_ir_diff_accepts_preserved_contract_surface():
    source = {
        "purpose": "Serve health API.",
        "public_interfaces": [{"kind": "route", "name": "/health"}],
        "behavior_contracts": [{"source": "app.py:health"}],
        "architecture_slices": [{"id": "health_slice"}],
        "acceptance_tests": [{"id": "AC1", "criterion": "returns ok"}],
        "domain_model": {"data_artifacts": ["sample.json"]},
    }
    target = {
        "purpose": "Serve health API.",
        "public_interfaces": [{"kind": "route", "name": "/health"}],
        "behavior_contracts": [{"source": "app.py:health"}],
        "architecture_slices": [{"id": "health_slice"}],
        "acceptance_tests": [{"id": "AC1", "criterion": "returns ok"}],
        "domain_model": {"data_artifacts": ["sample.json"]},
    }

    diff = compare_system_knowledge_ir(source, target)

    assert diff["status"] == "ok"
    assert diff["score"] == 1.0
    assert diff["losses"] == []


def test_system_knowledge_ir_diff_flags_lost_public_interface():
    diff = compare_system_knowledge_ir(
        {
            "purpose": "Serve health API.",
            "public_interfaces": [{"kind": "route", "name": "/health"}],
            "behavior_contracts": [{"source": "app.py:health"}],
        },
        {"purpose": "Serve health API.", "public_interfaces": [], "behavior_contracts": []},
    )

    assert diff["status"] == "needs_work"
    assert diff["summary"]["critical_loss_count"] == 2
    assert diff["losses"][0]["category"] == "public_interfaces"


def test_system_knowledge_ir_diff_ignores_purpose_inference_boilerplate():
    diff = compare_system_knowledge_ir(
        {"purpose": "Manage asynchronous callback signals with explicit registration, freeze, dispatch, and callback-error behavior."},
        {
            "purpose": (
                "Inferred from docs: Manage asynchronous callback signals with explicit registration, "
                "freeze, dispatch, and callback-error behavior. (Python automation/tooling project)."
            )
        },
    )

    assert not [loss for loss in diff["losses"] if loss["category"] == "purpose"]
