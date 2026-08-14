from runtime.evaluation_target_clamp import clamp_architecture_target


def _adr():
    return {
        "artifact_type": "ArchitectureDecisionRecord",
        "source_context": {"app.py:run": {"kind": "central_flow_node"}},
        "first_slice_contract": {"name": "default", "targets": ["app.py:other"], "steps": ["Verify target."]},
        "spec_writer_brief": {"files_or_symbols": ["app.py:other"]},
        "architecture_synthesis": {"recommended_first_slice": {"targets": ["app.py:other"]}},
    }


def test_clamp_uses_only_existing_source_context_target():
    result = clamp_architecture_target(_adr(), "app.py:run")

    assert result["first_slice_contract"]["targets"] == ["app.py:run"]
    assert result["spec_writer_brief"]["first_slice"]["targets"] == ["app.py:run"]
    assert result["architecture_synthesis"]["recommended_first_slice"]["targets"] == ["app.py:run"]
    assert result["evaluation_target_clamp"]["mode"] == "evaluation_only"


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
