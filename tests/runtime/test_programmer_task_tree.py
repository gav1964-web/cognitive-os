from __future__ import annotations

from runtime.programmer_task_tree import build_programmer_task_tree


def test_programmer_task_tree_builds_planning_handoff() -> None:
    tree = build_programmer_task_tree(
        technical_spec={"artifact_type": "TechnicalSpec", "role": "spec_writer"},
        implementation_plan={
            "artifact_type": "ImplementationPlan",
            "role": "implementer",
            "implementation_target": {"candidate": "pkg/core.py:run"},
            "patch_intent": {"target_symbol": "pkg/core.py:run"},
            "contract_binding": {"input_contract": {"name": "str"}},
            "expected_files": ["pkg/core.py"],
            "verification_commands": ["python -m compileall ."],
        },
        test_plan={"artifact_type": "TestPlan", "role": "tester", "executable_acceptance": {"obligations": [{"id": "O1"}]}},
    )

    assert tree["artifact_type"] == "ProgrammerTaskTree"
    assert tree["status"] == "ready"
    assert tree["authority"] == "planning_only_no_source_edit"
    assert tree["programmer_handoff"]["next_role"] == "sandbox_programmer"
    assert [node["action"] for node in tree["nodes"]] == [
        "bind_target",
        "prepare_writable_scope",
        "map_contract_inputs",
        "materialize_acceptance",
        "verify_and_handoff",
    ]
    assert [gate["id"] for gate in tree["verifier_gates"]] == [
        "sandbox_only",
        "writable_scope_only",
        "source_project_unchanged",
        "executable_acceptance",
        "allowed_verification_commands",
    ]


def test_programmer_task_tree_classifies_blocked_handoff() -> None:
    tree = build_programmer_task_tree(
        technical_spec={},
        implementation_plan={"implementation_target": {"status": "blocked_no_safe_candidate"}},
        test_plan={},
    )

    assert tree["status"] == "needs_review"
    assert tree["boundary"]["track"] == "blocked_handoff"
    assert tree["nodes"][0]["status"] == "needs_review"
