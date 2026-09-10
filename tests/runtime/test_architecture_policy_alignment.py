from runtime.architecture_policy_alignment import align_policy_selected_architecture


def test_policy_selected_target_becomes_architect_owned_first_slice():
    artifacts = {
        "adr": {
            "artifact_type": "ArchitectureDecisionRecord",
            "first_slice_contract": {"targets": ["app.py:old"], "steps": []},
            "spec_writer_brief": {},
        },
        "spec": {
            "artifact_type": "TechnicalSpec",
            "extraction_contract": {
                "candidate": "app.py:normalize",
                "selection_policy_ids": ["verified_policy"],
            },
            "source_evidence": [{"source": "app.py:normalize", "snippet": "return value"}],
        },
    }

    result = align_policy_selected_architecture(artifacts, {"summary": {}})

    first_slice = result["adr"]["first_slice_contract"]
    assert first_slice["targets"] == ["app.py:normalize"]
    assert first_slice["deferred_targets"] == ["app.py:old"]
    assert result["adr"]["first_slice_reselection_history"][0]["selection_policy_ids"] == [
        "verified_policy",
    ]


def test_policy_selected_target_without_source_evidence_is_not_aligned():
    artifacts = {
        "adr": {
            "artifact_type": "ArchitectureDecisionRecord",
            "first_slice_contract": {"targets": ["app.py:old"]},
        },
        "spec": {
            "artifact_type": "TechnicalSpec",
            "extraction_contract": {
                "candidate": "app.py:missing",
                "selection_policy_ids": ["verified_policy"],
            },
            "source_evidence": [],
        },
    }

    assert align_policy_selected_architecture(artifacts, {}) is artifacts
