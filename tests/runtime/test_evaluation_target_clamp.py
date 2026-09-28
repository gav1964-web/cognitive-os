from runtime.evaluation_target_clamp import clamp_architecture_target


def _adr():
    return {
        "artifact_type": "ArchitectureDecisionRecord",
        "source_context": {
            "app.py:run": {"kind": "central_flow_node"},
            "app.py:build": {"kind": "function"},
        },
        "first_slice_contract": {"name": "default", "targets": ["app.py:other"], "steps": ["Verify target."]},
        "spec_writer_brief": {"files_or_symbols": ["app.py:other"]},
        "architecture_synthesis": {"recommended_first_slice": {"targets": ["app.py:other"]}},
    }


def test_clamp_uses_only_existing_source_context_target():
    result = clamp_architecture_target(_adr(), "app.py:run")

    assert result["first_slice_contract"]["targets"] == ["app.py:run"]
    assert result["spec_writer_brief"]["first_slice"]["targets"] == ["app.py:run"]
    assert result["architecture_synthesis"]["recommended_first_slice"]["targets"] == ["app.py:run"]
    assert result["first_slice_contract"]["steps"] == [
        "Specify and verify `app.py:run` without changing project source."
    ]
    assert result["evaluation_target_clamp"]["mode"] == "evaluation_only"
    assert result["evaluation_target_clamp"]["candidate_pool"] == ["app.py:build"]


def test_clamp_rejects_unknown_target_without_mutation():
    artifact = _adr()

    assert clamp_architecture_target(artifact, "invented.py:run") is artifact


def test_clamp_accepts_exact_extracted_source_evidence():
    result = clamp_architecture_target(
        _adr(),
        "worker.py:sync_items",
        source_evidence={"source": "worker.py:sync_items", "snippet": {"text": "def sync_items(): pass"}},
    )

    assert "worker.py:sync_items" in result["source_context"]
    assert result["evaluation_target_clamp"]["source_context_verified"] is True


def test_clamp_candidate_pool_preserves_original_architect_target_first():
    artifact = _adr()
    artifact["first_slice_contract"]["targets"] = ["app.py:build"]
    artifact["source_context"]["app.py:other"] = {"kind": "function"}

    result = clamp_architecture_target(artifact, "app.py:run")

    assert result["evaluation_target_clamp"]["candidate_pool"] == [
        "app.py:build", "app.py:other",
    ]


def test_clamp_candidate_pool_prioritizes_standalone_returning_contract():
    artifact = _adr()
    artifact["source_context"] = {
        "app.py:run": {},
        "app.py:method": {"candidate_score": 100, "snippet": {
            "owner_class": "Service", "target_binding": "method_symbol",
            "structural_contract": {"return_paths": 1, "output_inference_basis": "return_expression"},
        }},
        "app.py:function": {"candidate_score": 50, "snippet": {
            "target_binding": "function_symbol",
            "structural_contract": {"return_paths": 1, "output_inference_basis": "return_expression"},
        }},
    }

    result = clamp_architecture_target(artifact, "app.py:run")

    assert result["evaluation_target_clamp"]["candidate_pool"] == [
        "app.py:function", "app.py:method",
    ]


def test_clamp_candidate_pool_demotes_property_accessor():
    artifact = _adr()
    artifact["source_context"] = {
        "app.py:run": {},
        "app.py:property_value": {"candidate_score": 100, "snippet": {
            "decorators": ["property"],
            "structural_contract": {
                "return_paths": 1,
                "output_inference_basis": "return_expression",
            },
        }},
        "app.py:normalize": {"candidate_score": 80, "snippet": {
            "structural_contract": {
                "return_paths": 1,
                "output_inference_basis": "return_expression",
            },
        }},
    }

    result = clamp_architecture_target(artifact, "app.py:run")

    assert result["evaluation_target_clamp"]["candidate_pool"] == [
        "app.py:normalize", "app.py:property_value",
    ]
