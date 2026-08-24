from runtime import foundation_executable_evidence as evidence


def _spec(*, effects=None, observed_effects=None, state_mutation=False, archetypes=None, contract_family=None):
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
            "contract_family": contract_family,
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


def test_foundation_evidence_allows_isolated_transitive_observability():
    result = evidence._eligibility(_spec(effects=["observability"]))

    assert result["status"] == "eligible"


def test_foundation_evidence_rejects_direct_memory_state_without_process_isolation():
    result = evidence._eligibility(
        _spec(effects=["memory_state"], observed_effects=["memory_state"])
    )

    assert result["status"] == "skipped"
    assert result["reason"] == "side_effectful_target"


def test_foundation_evidence_allows_direct_memory_state_in_process_isolation():
    result = evidence._eligibility(
        _spec(
            effects=["memory_state"],
            observed_effects=["memory_state"],
            state_mutation=True,
        ),
        process_isolated=True,
    )

    assert result["status"] == "eligible"


def test_foundation_evidence_rejects_external_effect_in_process_isolation():
    result = evidence._eligibility(
        _spec(effects=["filesystem_write"], observed_effects=["filesystem_write"]),
        process_isolated=True,
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


def test_foundation_evidence_allows_profiled_logging_adapter_factory():
    result = evidence._eligibility(_spec(
        effects=["observability"],
        observed_effects=["observability"],
        archetypes=["logging_adapter_factory"],
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


def test_foundation_evidence_allows_typed_external_api_command():
    result = evidence._eligibility(_spec(
        effects=["network"],
        contract_family="external_api_command_boundary",
    ))

    assert result["status"] == "eligible"


def test_foundation_evidence_allows_delegated_logging_projection_observability():
    result = evidence._eligibility(_spec(
        effects=["observability"],
        contract_family="logging_record_projection",
    ))

    assert result["status"] == "eligible"


def test_foundation_evidence_rejects_unprofiled_delegated_network_effect():
    result = evidence._eligibility(_spec(effects=["network"]))

    assert result["reason"] == "side_effectful_target"


def test_logging_sink_network_effect_requires_profiled_process_isolation():
    spec = _spec(
        effects=["network"],
        observed_effects=["network"],
        archetypes=["logging_sink_adapter"],
    )

    assert evidence._eligibility(spec)["reason"] == "side_effectful_target"
    assert evidence._eligibility(spec, process_isolated=True)["status"] == "eligible"


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


def test_foundation_evidence_uses_process_boundary_when_requested(monkeypatch, tmp_path):
    monkeypatch.setattr(evidence, "build_implementation_plan", lambda **kwargs: {})
    monkeypatch.setattr(
        evidence, "build_test_plan",
        lambda **kwargs: {"executable_acceptance": {"obligations": [{"id": "EA-1"}]}},
    )
    observed = {}

    def isolated(**kwargs):
        observed.update(kwargs)
        return {"status": "passed", "summary": {"signal_strength": "executable_callable"}}

    monkeypatch.setattr(evidence, "run_executable_acceptance_process", isolated)
    result = evidence.collect_foundation_executable_evidence(
        root=tmp_path,
        project_dir=tmp_path,
        technical_spec=_spec(
            effects=["memory_state"],
            observed_effects=["memory_state"],
            state_mutation=True,
        ),
        process_isolated=True,
    )

    assert observed["timeout_seconds"] == evidence.foundation_evidence_policy()[
        "isolated_process_timeout_seconds"
    ]
    assert observed["executable_policy"]["schema_version"] == "executable_acceptance_policy.v1"
    assert result["acceptance_signal"] == "executable_callable"


def test_shadow_target_admits_only_exact_low_risk_isolated_candidate():
    spec = _spec()
    contract = spec["extraction_contract"]
    contract["structural_evidence"].update({
        "source_body_available": True,
        "source_body_complete": True,
    })
    spec["first_slice_reselection_request"] = {
        "status": "required",
        "trigger": "low_first_slice_viability",
    }

    production = evidence._eligibility(spec, process_isolated=True)
    shadow = evidence._eligibility(
        spec, process_isolated=True, shadow_target="app.py:normalize",
    )

    assert production["reason"] == "first_slice_reselection_required"
    assert shadow["status"] == "eligible"
    assert shadow["shadow_target_admitted"] is True


def test_shadow_target_rejects_effectful_or_mismatched_candidate():
    spec = _spec(effects=["network"], observed_effects=["network"])
    spec["extraction_contract"]["structural_evidence"].update({
        "source_body_available": True,
        "source_body_complete": True,
    })
    spec["first_slice_reselection_request"] = {
        "status": "required",
        "trigger": "low_first_slice_viability",
    }

    effectful = evidence._eligibility(
        spec, process_isolated=True, shadow_target="app.py:normalize",
    )
    mismatched = evidence._eligibility(
        spec, process_isolated=True, shadow_target="app.py:other",
    )

    assert effectful["reason"] == "first_slice_reselection_required"
    assert mismatched["reason"] == "first_slice_reselection_required"


def test_promoted_selection_policy_admits_safe_reselection_in_production():
    spec = _spec()
    spec["extraction_contract"].update({
        "selection_policy_ids": ["verified_policy"],
        "structural_evidence": {
            "source_body_available": True, "source_body_complete": True,
            "observed_side_effects": [], "state_mutation": False,
        },
    })
    spec["first_slice_reselection_request"] = {
        "status": "required", "trigger": "low_first_slice_viability",
    }

    result = evidence._eligibility(spec, process_isolated=True)

    assert result["status"] == "eligible"
    assert result["selection_policy_target_admitted"] is True


def test_promoted_policy_admits_conservative_memory_effect_in_process():
    spec = _spec()
    spec["extraction_contract"].update({
        "selection_policy_ids": ["verified_policy"],
        "side_effects": {"declared": ["memory_state"]},
        "structural_evidence": {
            "source_body_available": True,
            "source_body_complete": True,
            "observed_side_effects": [],
            "state_mutation": False,
        },
    })
    spec["first_slice_reselection_request"] = {
        "status": "required", "trigger": "low_first_slice_viability",
    }

    result = evidence._eligibility(spec, process_isolated=True)

    assert result["status"] == "eligible"
    assert result["selection_policy_target_admitted"] is True
