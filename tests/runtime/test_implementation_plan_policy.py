from __future__ import annotations

from runtime.role_skills import run_role_skill


def test_implementer_blocks_context_only_technical_spec_target():
    spec = _context_only_spec()

    plan = run_role_skill("implementer", technical_spec=spec)

    assert plan["implementation_target"]["status"] == "blocked_no_safe_candidate"
    assert plan["implementation_target"]["candidate"] is None
    assert plan["implementation_target"]["rejected_candidate"] == spec["extraction_contract"]["candidate"]
    assert "context_only_implementation_target" in plan["implementation_target"]["blocked_by"]
    assert plan["contract_binding"]["binding_status"] == "blocked_no_safe_candidate"
    assert plan["writable_scope"] == []
    assert plan["patch_intent"]["status"] == "blocked_no_safe_candidate"


def test_reviewer_preserves_context_only_block_without_drift_noise():
    spec = _context_only_spec()
    implementation = run_role_skill("implementer", technical_spec=spec)
    test_plan = run_role_skill("tester", technical_spec=spec, implementation_plan=implementation)

    review = run_role_skill("reviewer", technical_spec=spec, implementation_plan=implementation, test_plan=test_plan)

    assert review["review_target"]["binding_status"] == "blocked_no_safe_candidate"
    assert review["contract_violations"] == []
    assert review["architecture_drift"] == []
    assert review["recommendation"] == "request_rework"


def _context_only_spec() -> dict:
    return {
        "artifact_type": "TechnicalSpec",
        "role": "spec_writer",
        "requirements": [{"id": "REQ-001", "statement": "keep cluster setup deterministic"}],
        "acceptance_criteria": [{"id": "AC-001", "criterion": "target is bounded", "verification": "review"}],
        "implementation_handoff": {
            "patch_scope": ["integration_tests/python_modules/pkg/kind.py:create_cluster"],
        },
        "extraction_contract": {
            "candidate": "integration_tests/python_modules/pkg/kind.py:create_cluster",
            "candidate_score": 92,
            "selection_reason": "source-backed but context-only",
            "input_contract": {"name": "str"},
            "output_contract": {"result": "Cluster"},
            "side_effects": {"declared": ["subprocess"], "requires_process_boundary": True},
            "evidence_source": "integration_tests/python_modules/pkg/kind.py:create_cluster",
        },
    }
