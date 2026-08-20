from runtime import foundation_executable_evidence as evidence


def _spec(*, effects=None, observed_effects=None, state_mutation=False, archetypes=None):
    return {
        "artifact_type": "TechnicalSpec",
        "extraction_contract": {
            "candidate": "app.py:normalize",
            "structural_evidence": {
                "state_mutation": state_mutation,
                "observed_side_effects": list(observed_effects or []),
            },
            "side_effects": {"declared": list(effects or [])},
            "semantic_quality": {"contract_archetype_ids": list(archetypes or [])},
        },
    }


def test_foundation_evidence_skips_side_effectful_target(monkeypatch, tmp_path):
    monkeypatch.setattr(
        evidence,
        "run_executable_acceptance",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not execute")),
    )

    result = evidence.collect_foundation_executable_evidence(
        root=tmp_path, project_dir=tmp_path, technical_spec=_spec(effects=["filesystem_write"])
    )

    assert result["status"] == "skipped"
    assert result["reason"] == "side_effectful_target"


def test_foundation_evidence_allows_isolated_transitive_memory_state():
    result = evidence._eligibility(_spec(effects=["memory_state"]))

    assert result["status"] == "eligible"


def test_foundation_evidence_rejects_direct_memory_state():
    result = evidence._eligibility(
        _spec(effects=["memory_state"], observed_effects=["memory_state"])
    )

    assert result["status"] == "skipped"
    assert result["reason"] == "side_effectful_target"


def test_foundation_evidence_allows_profiled_direct_observability():
    result = evidence._eligibility(_spec(
        effects=["observability"],
        observed_effects=["observability"],
        archetypes=["observability_render_command"],
    ))

    assert result["status"] == "eligible"


def test_foundation_evidence_rejects_unprofiled_direct_observability():
    result = evidence._eligibility(_spec(
        effects=["observability"], observed_effects=["observability"]
    ))

    assert result["reason"] == "side_effectful_target"


def test_foundation_evidence_allows_profiled_typed_object_loader():
    result = evidence._eligibility(_spec(
        effects=["filesystem_read"],
        observed_effects=["filesystem_read"],
        archetypes=["filesystem_typed_object_loader"],
    ))

    assert result["status"] == "eligible"


def test_foundation_evidence_propagates_executable_callable(monkeypatch, tmp_path):
    monkeypatch.setattr(evidence, "build_implementation_plan", lambda **kwargs: {"artifact_type": "ImplementationPlan"})
    monkeypatch.setattr(
        evidence,
        "build_test_plan",
        lambda **kwargs: {"executable_acceptance": {"obligations": [{"id": "EA-1"}]}},
    )
    monkeypatch.setattr(
        evidence,
        "run_executable_acceptance",
        lambda **kwargs: {
            "status": "passed",
            "summary": {"signal_strength": "executable_callable", "callable_harness_count": 1},
            "source_code_changes": False,
        },
    )

    result = evidence.collect_foundation_executable_evidence(
        root=tmp_path, project_dir=tmp_path, technical_spec=_spec()
    )

    assert result["status"] == "passed"
    assert result["acceptance_signal"] == "executable_callable"
