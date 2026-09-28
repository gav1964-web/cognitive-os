import json

from runtime.self_improvement_failure_evidence import artifact_evidence, capability_signature, reselection_exhausted


def test_terminal_reselection_evidence_marks_candidate_search_exhausted(tmp_path):
    spec = tmp_path / "TechnicalSpec.json"
    spec.write_text(json.dumps({
        "extraction_contract": {"candidate": "script.py", "ranked_candidates": []},
        "first_slice_reselection_request": {
            "status": "required",
            "terminal": True,
            "resolution_status": "exhausted",
            "outcome": {
                "status": "exhausted",
                "expanded_candidate_count": 0,
                "selected_targets": [],
            },
        },
    }), encoding="utf-8")

    evidence = artifact_evidence({"technical_spec": {"path": str(spec)}})
    packet = {"artifact_evidence": evidence}

    assert evidence["technical_spec"]["reselection"]["terminal"] is True
    assert reselection_exhausted(packet) is True
    assert capability_signature(packet).startswith("unknown|unclassified|")


def test_architecture_evidence_carries_safety_ranked_source_candidate_pool(tmp_path):
    adr = tmp_path / "ArchitectureDecisionRecord.json"
    adr.write_text(json.dumps({
        "first_slice_contract": {"targets": ["app.py:write"]},
        "source_context": {
            "app.py:write": {
                "side_effects": ["observability"],
                "snippet": {"target_binding": "function_symbol", "structural_contract": {
                    "return_paths": 0, "output_inference_basis": "no_value_return",
                }},
            },
            "app.py:build": {
                "dependency_readiness": {"status": "ready"},
                "snippet": {"target_binding": "function_symbol", "structural_contract": {
                    "return_paths": 1, "output_inference_basis": "return_expression",
                }},
            },
        },
    }), encoding="utf-8")

    evidence = artifact_evidence({"architecture_decision": {"path": str(adr)}})

    assert evidence["architecture_decision"]["source_candidate_pool"] == [
        "app.py:build", "app.py:write",
    ]


def test_architecture_evidence_accepts_source_text_snippets(tmp_path):
    adr = tmp_path / "ArchitectureDecisionRecord.json"
    adr.write_text(json.dumps({
        "source_context": {
            "app.py:build": {
                "snippet": "def build(value):\n    return value",
                "target_binding": "function_symbol",
                "structural_contract": {
                    "return_paths": 1,
                    "output_inference_basis": "return_expression",
                },
            },
        },
    }), encoding="utf-8")

    evidence = artifact_evidence({"architecture_decision": {"path": str(adr)}})

    assert evidence["architecture_decision"]["source_candidate_pool"] == ["app.py:build"]
