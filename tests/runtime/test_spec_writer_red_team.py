from __future__ import annotations

from runtime.spec_writer_red_team import red_team_technical_spec


def test_spec_writer_red_team_accepts_domain_contract_with_gates():
    spec = {
        "artifact_type": "TechnicalSpec",
        "requirements": [
            {
                "statement": "First-slice `repair_attempt_contract_slice` must define the LLM repair hypothesis contract.",
                "source": "ProjectArchitectureSynthesis.recommended_first_slice",
            }
        ],
        "acceptance_criteria": [
            {
                "criterion": "AutoFix/auto_dev_agent.py:send_to_model rejects invalid_model_json with evidence.",
                "source": "AutoFix/auto_dev_agent.py:send_to_model",
            }
        ],
        "traceability_table": [
            {
                "source": "ProjectArchitectureSynthesis.recommended_first_slice",
                "requirement": "repair_attempt_contract_slice",
                "acceptance_id": "AC-001",
            }
        ],
        "work_plan_contract": {
            "name": "repair_attempt_contract_slice",
            "obligations": [
                {
                    "id": "WPC-001",
                    "step": "Define the LLM repair hypothesis contract.",
                    "target": "AutoFix/auto_dev_agent.py:send_to_model",
                }
            ],
        },
        "interface_contracts": [
            {
                "source": "AutoFix/auto_dev_agent.py:send_to_model",
                "input_contract": {"failure_evidence": "FailureEvidence"},
                "output_contract": {"model_patch_proposal": "ModelPatchProposal"},
            }
        ],
        "extraction_contract": {
            "candidate": "AutoFix/auto_dev_agent.py:send_to_model",
            "contract_family": "llm_repair_hypothesis_boundary",
            "input_contract": {"failure_evidence": "FailureEvidence"},
            "output_contract": {"model_patch_proposal": "ModelPatchProposal"},
            "side_effects": {"declared": ["filesystem"], "requires_validation_gate": True},
        },
    }
    adr = {"first_slice_contract": {"name": "repair_attempt_contract_slice"}}

    report = red_team_technical_spec(spec, adr)

    assert report["status"] == "pass"
    assert report["handoff_verdict"] == "ready_for_implementer"


def test_spec_writer_red_team_blocks_weak_any_contract():
    spec = {
        "artifact_type": "TechnicalSpec",
        "requirements": [{"statement": "Prepare specific implementation contract."}],
        "acceptance_criteria": [{"criterion": "pkg/main.py:run produces expected result.", "source": "pkg/main.py:run"}],
        "traceability_table": [{"source": "REQ-001", "acceptance_id": "AC-001"}],
        "work_plan_contract": {
            "name": "first_slice",
            "obligations": [{"id": "WPC-001", "step": "Implement bounded step.", "target": "pkg/main.py:run"}],
        },
        "interface_contracts": [
            {"source": "pkg/main.py:run", "input_contract": {"payload": "Any"}, "output_contract": {"result": "Any"}}
        ],
        "extraction_contract": {
            "candidate": "pkg/main.py:run",
            "input_contract": {"payload": "Any"},
            "output_contract": {"result": "Any"},
            "side_effects": {"declared": ["filesystem"]},
        },
    }

    report = red_team_technical_spec(spec, {"first_slice_contract": {"name": "first_slice"}})

    assert report["status"] == "fail"
    assert report["handoff_verdict"] == "return_to_spec_writer"
    assert "weak_any_contract" in {row["code"] for row in report["blocking_findings"]}


def test_spec_writer_red_team_accepts_explicit_no_safe_candidate_block():
    spec = {
        "artifact_type": "TechnicalSpec",
        "work_plan_contract": {
            "status": "blocked_no_first_slice",
            "blocked_by": ["no_safe_source_specific_candidate"],
        },
        "extraction_contract": {
            "status": "blocked_no_safe_candidate",
            "candidate": None,
            "blocked_by": ["no_safe_source_specific_candidate"],
            "input_contract": {},
            "output_contract": {},
        },
    }

    report = red_team_technical_spec(spec, {"first_slice_contract": {"targets": []}})

    assert report["status"] == "pass"
    assert report["handoff_verdict"] == "blocked_no_safe_candidate"
    assert report["score"] == 1.0
