from runtime.self_improvement_plugin_foundry import resolve_plugin_requests


def _request():
    return {
        "request_id": "cdr_test",
        "missing_capability": "candidate_selection_discriminator_plugin",
    }


def test_foundry_resolves_registered_plugin_and_measured_rejection():
    report = resolve_plugin_requests([_request()], [{
        "project": "holdout",
        "improvement_plugin_cycle": {"attempts": [{
            "plugin_id": "candidate_selection_discriminator",
            "status": "blocked",
            "reason": "shadow_discriminator_not_confirmed",
        }]},
    }])

    assert report["status"] == "candidate_rejected"
    assert report["resolutions"][0]["plugin_id"] == "candidate_selection_discriminator"
    assert report["resolutions"][0]["attempt_outcomes"][0]["project"] == "holdout"


def test_foundry_never_claims_unregistered_capability():
    report = resolve_plugin_requests([{
        "request_id": "cdr_unknown", "missing_capability": "unknown_plugin",
    }], [])

    assert report["status"] == "implementation_required"
    assert report["runtime_patch_auto_promotion"] is False


def test_foundry_routes_bounded_target_discovery_to_measured_plugin():
    report = resolve_plugin_requests([{
        "request_id": "cdr_target_discovery",
        "missing_capability": "bounded_executable_target_discovery_or_sandbox_adapter",
    }], [{
        "project": "holdout",
        "improvement_plugin_cycle": {"attempts": [{
            "plugin_id": "candidate_selection_discriminator",
            "status": "trial_passed",
        }]},
    }])

    assert report["status"] == "trial_passed"
    assert report["resolutions"][0]["plugin_id"] == "candidate_selection_discriminator"
    assert report["resolutions"][0]["plugin_version"] == "1.3.0"


def test_foundry_routes_structural_synthesis_to_admission_plugin():
    report = resolve_plugin_requests([{
        "request_id": "cdr_structural",
        "missing_capability": "candidate_selection_structural_discriminator_synthesis",
    }], [{
        "project": "holdout",
        "improvement_plugin_cycle": {"attempts": [{
            "plugin_id": "candidate_selection_admission",
            "status": "trial_passed",
        }]},
    }])

    assert report["status"] == "trial_passed"
    assert report["resolutions"][0]["plugin_id"] == "candidate_selection_admission"
    assert report["resolutions"][0]["plugin_version"] == "1.2.0"


def test_foundry_counts_one_best_attempt_per_independent_project():
    reports = [{
        "project": "same-project",
        "improvement_plugin_cycle": {"attempts": [{
            "plugin_id": "candidate_selection_discriminator", "status": "blocked",
        }]},
        "post_training_admission": {"attempts": [{
            "plugin_id": "candidate_selection_discriminator", "status": "trial_passed",
        }]},
    }, {
        "project": "same-project",
        "improvement_plugin_cycle": {"attempts": [{
            "plugin_id": "candidate_selection_discriminator", "status": "blocked",
        }]},
    }]

    report = resolve_plugin_requests([_request()], reports)

    assert report["resolutions"][0]["attempt_count"] == 1
    assert report["resolutions"][0]["attempt_outcomes"] == [{
        "project": "same-project", "status": "trial_passed", "reason": None,
    }]
