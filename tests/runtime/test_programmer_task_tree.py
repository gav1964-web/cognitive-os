from __future__ import annotations

import json

import pytest

from runtime.programmer_task_tree import build_programmer_task_tree, load_programmer_task_tree_policy


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
            "change_plan": [
                {"id": "CHANGE-001", "kind": "contract_shape", "target": "pkg/core.py:run", "instruction": "Preserve input and output."},
                {"id": "CHANGE-002", "kind": "requirement_delta", "target": "pkg/core.py:run", "instruction": "Normalize the name."},
            ],
            "acceptance_mapping": [{"acceptance_id": "AC-001", "verification": "Assert normalized output."}],
            "quality_gates": [{"id": "GATE-001"}],
            "verification_commands": ["python -m compileall ."],
        },
        test_plan={"artifact_type": "TestPlan", "role": "tester", "executable_acceptance": {"obligations": [{"id": "O1"}]}},
    )

    assert tree["artifact_type"] == "ProgrammerTaskTree"
    assert tree["status"] == "ready"
    assert tree["authority"] == "planning_only_no_source_edit"
    assert tree["role"] == "task_tree_builder"
    assert tree["programmer_handoff"]["next_role"] == "programmer_executor"
    assert [node["id"] for node in tree["nodes"]] == [
        "SCOPE", "CHANGE-001", "CHANGE-002", "ACCEPT-001", "VERIFY", "HANDOFF"
    ]
    assert tree["nodes"][2]["depends_on"] == ["CHANGE-001"]
    assert tree["nodes"][3]["acceptance_ids"] == ["AC-001"]
    assert tree["coverage"]["unmapped_acceptance_ids"] == []
    assert tree["summary"]["dependency_edge_count"] == 5
    assert [gate["id"] for gate in tree["verifier_gates"]] == [
        "sandbox_only",
        "writable_scope_only",
        "source_project_unchanged",
        "GATE-001",
        "executable_acceptance",
    ]


def test_programmer_task_tree_classifies_blocked_handoff() -> None:
    tree = build_programmer_task_tree(
        technical_spec={},
        implementation_plan={"implementation_target": {"status": "blocked_no_safe_candidate"}},
        test_plan={"executable_acceptance": {"obligations": [{"id": "OBL-BLOCKED"}]}},
    )

    assert tree["status"] == "needs_review"
    assert tree["boundary"]["track"] == "blocked_handoff"
    assert tree["nodes"][0]["status"] == "needs_review"
    assert tree["nodes"][0]["action"] == "preserve_no_patch_handoff"
    assert tree["nodes"][0]["acceptance_ids"] == ["OBL-BLOCKED"]
    assert tree["coverage"]["unmapped_acceptance_ids"] == []
    assert tree["coverage"]["all_changes_traced"] is True


def test_programmer_task_tree_policy_rejects_unknown_schema(tmp_path) -> None:
    path = tmp_path / "policy.json"
    path.write_text(json.dumps({"schema_version": "unknown"}), encoding="utf-8")

    with pytest.raises(ValueError, match="programmer_task_tree_policy.v1"):
        load_programmer_task_tree_policy(str(path))
