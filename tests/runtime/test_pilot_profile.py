from runtime.pilot_profile import evaluate_pilot_candidate, load_pilot_profile


def _readiness():
    profile = load_pilot_profile()
    return {"roles": {role: {"mvp_ready": True} for role in profile["required_roles"]}}


def test_pilot_admits_only_bounded_transfer_evidence() -> None:
    decision = evaluate_pilot_candidate(
        project_stratum="library_pure_transform",
        risk_profiles=["deterministic"],
        effect_mode="pure",
        requested_mode="sandbox_patch",
        role_readiness=_readiness(),
        transfer_evidence={"blind_projects": 2, "independent_lineages": 2, "handoff_loss": 0},
        reviewer_adversarial={"status": "ok"},
    )

    assert decision["status"] == "eligible"
    assert decision["execution_policy"]["source_apply_allowed"] is False


def test_pilot_admits_deterministic_framework_plugin_sandbox() -> None:
    decision = evaluate_pilot_candidate(
        project_stratum="framework_plugin_build",
        risk_profiles=["deterministic"],
        effect_mode="sandbox_only",
        requested_mode="sandbox_patch",
        role_readiness=_readiness(),
        transfer_evidence={"blind_projects": 3, "independent_lineages": 3, "handoff_loss": 0},
        reviewer_adversarial={"status": "ok"},
    )

    assert decision["status"] == "eligible"
    assert decision["execution_policy"]["source_apply_allowed"] is False


def test_pilot_blocks_network_and_missing_transfer() -> None:
    decision = evaluate_pilot_candidate(
        project_stratum="sdk_provider_integration",
        risk_profiles=["network"],
        effect_mode="filesystem_read",
        requested_mode="sandbox_patch",
        role_readiness=_readiness(),
        transfer_evidence={"blind_projects": 0, "independent_lineages": 0, "handoff_loss": 0},
        reviewer_adversarial={"status": "ok"},
    )

    assert decision["status"] == "blocked"
    assert "risk_profile_allowed" in decision["blocking_reasons"]
    assert "blind_project_floor_met" in decision["blocking_reasons"]
