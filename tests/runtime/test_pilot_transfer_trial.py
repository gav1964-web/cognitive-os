from runtime.pilot_transfer_trial import evaluate_pilot_transfer_trial
from runtime.pilot_profile import load_pilot_profile


def test_pilot_transfer_requires_two_independent_executable_cases() -> None:
    profile = load_pilot_profile()
    selection = {
        "selection_frozen": True,
        "projects": [
            {"full_name": "one/tool", "stratum": "cli_local_tool"},
            {"full_name": "two/parser", "stratum": "library_pure_transform"},
        ],
    }
    cases = []
    for project, stratum in (("one__tool", "cli_local_tool"), ("two__parser", "library_pure_transform")):
        cases.append({
            "project": project,
            "status": "ok",
            "quality_score": 1.0,
            "failed_checks": [],
            "source_code_changes": False,
            "project_classification": {"project_stratum": stratum, "risk_profiles": ["deterministic"]},
            "effect_mode": "pure",
            "executor": {"acceptance_signal": "executable_callable", "callable_harness_count": 1, "executable_acceptance": "passed"},
        })
    readiness = {"roles": {role: {"mvp_ready": True} for role in profile["required_roles"]}}

    report = evaluate_pilot_transfer_trial(
        selection=selection,
        full_chain_report={"cases": cases},
        role_readiness=readiness,
        reviewer_adversarial={"status": "ok"},
    )

    assert report["status"] == "eligible"
    assert report["transfer_evidence"] == {"blind_projects": 2, "independent_lineages": 2, "handoff_loss": 0}
    assert report["safety"]["source_apply_allowed"] is False
