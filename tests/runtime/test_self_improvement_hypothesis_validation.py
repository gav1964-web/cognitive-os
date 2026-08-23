from pathlib import Path

from runtime.self_improvement_hypothesis_validation import (
    _signatures_match,
    build_validation_plan,
    run_hypothesis_validation,
)
from runtime.self_improving_foundation_trial import run_self_improving_foundation_trial


def _training_report(project="source"):
    return {
        "project": project,
        "status": "candidate_improvement_confirmed",
        "knowledge_candidate_path": f"artifacts/{project}.json",
        "diagnosis": {"failure_class": "side_effectful_target"},
        "baseline": {
            "downstream_evidence": {"reason": "side_effectful_target"},
            "selected_candidate_quality": {"structural_evidence": {
                "observed_side_effects": ["memory_state"],
                "output_inference_basis": "no_value_return",
            }},
        },
        "improvement_plugin_cycle": {"promotion_count": 0},
    }


def _policy():
    return {"hypothesis_holdout": {
        "provider": "gitlab", "plan_version": "test.v1",
        "minimum_projects": 2, "maximum_projects": 3,
        "maximum_search_pages": 2,
        "query_profiles": {"side_effectful_target": ["state management", "command handler"]},
    }}


def test_validation_plan_is_portable_and_excludes_training_project():
    plan = build_validation_plan([_training_report("private_project")], _policy())

    assert plan["failure_class"] == "side_effectful_target"
    assert plan["plan_version"] == "test.v1"
    assert plan["portable_signature"] == "side_effectful_target|memory_state|no_value_return"
    assert plan["queries"] == ["state management", "command handler"]
    assert plan["providers"] == ["gitlab"]
    assert plan["excluded_projects"] == ["private_project"]
    assert "private_project" not in plan["portable_signature"]


def test_validation_plan_builds_queries_from_signature_terms():
    policy = _policy()
    policy["hypothesis_holdout"]["signature_query_terms"] = {
        "maximum_queries": 3,
        "effects": {"memory_state": ["state registry", "state accumulator"]},
        "output_bases": {"no_value_return": ["command handler", "event handler"]},
    }

    plan = build_validation_plan([_training_report()], policy)

    assert plan["queries"] == [
        "state registry",
        "command handler",
        "state management",
    ]


def test_validation_plan_carries_provider_policy_overrides():
    policy = _policy()
    policy["hypothesis_holdout"]["provider_policy_overrides"] = {
        "github": {"minimum_stars": 20},
    }

    plan = build_validation_plan([_training_report()], policy)

    assert plan["provider_policy_overrides"] == {"github": {"minimum_stars": 20}}


def test_validation_plan_carries_structural_prescreen_policy():
    policy = _policy()
    policy["hypothesis_holdout"]["structural_prescreen"] = {
        "enabled": True, "maximum_shortlist_projects": 6,
    }

    plan = build_validation_plan([_training_report()], policy)

    assert plan["structural_prescreen"] == {
        "enabled": True, "maximum_shortlist_projects": 6,
    }


def test_validation_plan_normalizes_equivalent_void_output_evidence():
    policy = _policy()
    policy["hypothesis_holdout"]["signature_normalization"] = {
        "output_basis_families": {
            "void_side_effect": ["no_value_return", "explicit_none_annotation"],
        },
    }

    plan = build_validation_plan([_training_report()], policy)

    assert plan["portable_signature"] == "side_effectful_target|memory_state|void_side_effect"
    assert plan["diagnosis_envelope"]["required_effects"] == ["memory_state"]
    assert plan["diagnosis_envelope"]["accepted_output_bases"] == [
        "explicit_none_annotation", "no_value_return", "void_side_effect",
    ]


def test_validation_queries_compose_effect_and_output_terms():
    policy = _policy()
    policy["hypothesis_holdout"].update({
        "query_composition": {"enabled": True, "maximum_queries": 1},
        "signature_query_terms": {
            "maximum_queries": 3,
            "effects": {"memory_state": ["state registry"]},
            "output_bases": {"no_value_return": ["command handler"]},
        },
    })

    plan = build_validation_plan([_training_report()], policy)

    assert plan["queries"] == [
        "state registry command handler", "state registry", "state management",
    ]


def test_signature_match_accepts_additional_effects_only_in_subset_mode():
    expected = "side_effectful_target|memory_state|void_side_effect"
    actual = "side_effectful_target|memory_state,observability|void_side_effect"

    assert _signatures_match(actual, expected, {"effect_match_mode": "required_subset"})
    assert not _signatures_match(actual, expected, {})


def test_signature_match_keeps_output_family_strict():
    expected = "side_effectful_target|memory_state|void_side_effect"
    actual = "side_effectful_target|memory_state|explicit_return_annotation"

    assert not _signatures_match(actual, expected, {"effect_match_mode": "required_subset"})


def test_hypothesis_validation_trains_sequential_independent_holdouts(tmp_path: Path):
    projects = [tmp_path / name for name in ("holdout_one", "holdout_two", "holdout_three")]
    for project in projects:
        project.mkdir()
    trained = []

    def trainer(**kwargs):
        trained.append(kwargs["project_dir"].name)
        promoted = kwargs["project_dir"].name == "holdout_two"
        return {
            "project": kwargs["project_dir"].name,
            "status": "candidate_improvement_confirmed",
            "post_training_admission": {"promotion_count": int(promoted)},
            "trained_attempt": {"project_min_score": 9.7},
        }

    result = run_hypothesis_validation(
        root=tmp_path, training=[_training_report()], discover=lambda _plan: projects,
        trainer=trainer, target_score=9.7, regression_projects=[],
        promote_config=True, write=False, policy=_policy(),
    )

    assert result["status"] == "completed"
    assert result["decision"] == "hypothesis_promoted"
    assert result["promotion_count"] == 1
    assert trained == ["holdout_one", "holdout_two", "holdout_three"]


def test_foundation_trial_automatically_validates_staged_hypothesis(monkeypatch, tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    holdouts = [tmp_path / name for name in (
        "holdout_one", "holdout_two", "holdout_three", "holdout_four",
    )]
    for path in holdouts:
        path.mkdir()
    baseline = {"status": "needs_work", "cases": [{
        "project": "source", "project_dir": str(source),
        "status": "ok", "project_min_score": 8.8,
    }]}
    verified = {"status": "ok", "cases": [{
        "project": "source", "project_dir": str(source),
        "status": "ok", "project_min_score": 9.7,
    }]}
    measurements = iter([baseline, verified])
    monkeypatch.setattr(
        "runtime.self_improving_foundation_trial.run_role_foundation_field_trial",
        lambda **_kwargs: next(measurements),
    )

    def trainer(**kwargs):
        project = kwargs["project_dir"].name
        if project == "source":
            return _training_report(project)
        return {
            "project": project, "status": "candidate_improvement_confirmed",
            "post_training_admission": {"promotion_count": int(project == "holdout_four")},
            "trained_attempt": {"project_min_score": 9.7},
        }

    result = run_self_improving_foundation_trial(
        root=tmp_path, project_roots=[tmp_path], max_training_projects=1,
        max_iterations=1, write=False, _trainer=trainer,
        _holdout_discoverer=lambda _plan: holdouts,
    )

    validation = result["iterations"][0]["hypothesis_validation"]
    assert result["status"] == "target_verified"
    assert validation["decision"] == "hypothesis_promoted"
    assert result["summary"]["hypothesis_holdout_project_count"] == 4


def test_external_discovery_failure_is_reported_without_crashing(tmp_path: Path):
    def fail(_plan):
        raise RuntimeError("rate limited")

    result = run_hypothesis_validation(
        root=tmp_path, training=[_training_report()], discover=fail,
        trainer=lambda **_kwargs: {}, target_score=9.7, regression_projects=[],
        promote_config=True, write=False, policy=_policy(),
    )

    assert result["status"] == "blocked"
    assert result["reason"] == "external_discovery_failed"
    assert "rate limited" in result["error"]


def test_validation_trains_only_structurally_matched_holdouts(tmp_path: Path):
    projects = [tmp_path / name for name in ("matching_one", "unrelated", "matching_two")]
    for project in projects:
        project.mkdir()
    trained = []

    def probe(**kwargs):
        project = kwargs["project_dir"].name
        matches = project != "unrelated"
        return {
            "source_fingerprint": "unchanged", "baseline": {
                "project_min_score": 8.0,
                "downstream_evidence": {
                    "reason": "side_effectful_target" if matches else "dependency_boundary",
                },
                "selected_candidate_quality": {"structural_evidence": {
                    "observed_side_effects": ["memory_state"],
                    "output_inference_basis": "no_value_return",
                }},
            },
            "diagnosis": {"failure_class": "dependency_boundary"},
        }

    def trainer(**kwargs):
        trained.append(kwargs["project_dir"].name)
        assert kwargs["prepared_probe"]["source_fingerprint"] == "unchanged"
        return {"status": "hypothesis_not_confirmed"}

    result = run_hypothesis_validation(
        root=tmp_path, training=[_training_report()], discover=lambda _plan: projects,
        trainer=trainer, probe=probe, target_score=9.7, regression_projects=[],
        promote_config=True, write=True, policy=_policy(),
    )

    assert result["status"] == "completed"
    assert result["matching_project_count"] == 2
    assert trained == ["matching_one", "matching_two"]
    assert Path(result["report_path"]).is_file()


def test_validation_blocks_without_two_diagnosis_matches(tmp_path: Path):
    projects = [tmp_path / name for name in ("one", "two", "three")]
    for project in projects:
        project.mkdir()

    result = run_hypothesis_validation(
        root=tmp_path, training=[_training_report()], discover=lambda _plan: projects,
        trainer=lambda **_kwargs: (_ for _ in ()).throw(AssertionError("must not train")),
        probe=lambda **_kwargs: {
            "baseline": {
                "project_min_score": 7.5,
                "downstream_evidence": {"reason": "dependency_boundary"},
            },
            "diagnosis": {"failure_class": "dependency_boundary"},
        },
        target_score=9.7, regression_projects=[], promote_config=True,
        write=False, policy=_policy(),
    )

    assert result["status"] == "blocked"
    assert result["reason"] == "insufficient_matching_holdouts"
    assert result["matching_project_count"] == 0
    assert result["recovery_metrics"]["matching_yield"] == 0.0
    assert result["recovery_metrics"]["same_failure_class_project_count"] == 0


def test_validation_rejects_same_failure_class_with_different_signature(tmp_path: Path):
    projects = [tmp_path / name for name in ("one", "two")]
    for project in projects:
        project.mkdir()

    result = run_hypothesis_validation(
        root=tmp_path, training=[_training_report()], discover=lambda _plan: projects,
        trainer=lambda **_kwargs: (_ for _ in ()).throw(AssertionError("must not train")),
        probe=lambda **_kwargs: {
            "baseline": {
                "project_min_score": 8.8,
                "downstream_evidence": {"reason": "side_effectful_target"},
                "selected_candidate_quality": {"structural_evidence": {
                    "observed_side_effects": ["filesystem_read"],
                    "output_inference_basis": "return_expression",
                }},
            },
            "diagnosis": {"failure_class": "side_effectful_target"},
        },
        target_score=9.7, regression_projects=[], promote_config=True,
        write=False, policy=_policy(),
    )

    assert result["reason"] == "insufficient_matching_holdouts"
    assert not any(row["matches_hypothesis"] for row in result["probe_results"])


def test_repeated_matching_failures_request_capability_development(monkeypatch, tmp_path: Path):
    projects = [tmp_path / name for name in ("one", "two")]
    for project in projects:
        project.mkdir()
    request = {"request_id": "cdr_test", "missing_capability": "new_plugin"}
    monkeypatch.setattr(
        "runtime.self_improvement_hypothesis_validation.capability_development_requests",
        lambda *_args, **_kwargs: [request],
    )

    result = run_hypothesis_validation(
        root=tmp_path, training=[_training_report()], discover=lambda _plan: projects,
        trainer=lambda **kwargs: {
            "project": kwargs["project_dir"].name,
            "status": "hypothesis_not_confirmed",
        },
        target_score=9.7, regression_projects=[], promote_config=True,
        write=False, policy=_policy(),
    )

    assert result["decision"] == "capability_development_required"
    assert result["capability_development_requests"] == [request]


def test_validation_retries_discovery_until_two_signature_matches(tmp_path: Path):
    batches = []
    for names in (("wrong_one", "wrong_two"), ("match_one", "match_two", "unused")):
        batch = [tmp_path / name for name in names]
        for project in batch:
            project.mkdir()
        batches.append(batch)
    plans = []
    events = []
    trained = []

    def discover(plan):
        plans.append(plan)
        return batches[len(plans) - 1]

    def probe(**kwargs):
        matches = kwargs["project_dir"].name.startswith("match_")
        return {
            "source_fingerprint": "unchanged",
            "baseline": {
                "project_min_score": 8.0,
                "downstream_evidence": {"reason": "side_effectful_target"},
                "selected_candidate_quality": {"structural_evidence": {
                    "observed_side_effects": ["memory_state" if matches else "filesystem_read"],
                    "output_inference_basis": "no_value_return" if matches else "return_expression",
                }},
            },
            "diagnosis": {"failure_class": "side_effectful_target"},
        }

    policy = _policy()
    policy["hypothesis_holdout"]["maximum_discovery_rounds"] = 3
    result = run_hypothesis_validation(
        root=tmp_path, training=[_training_report()], discover=discover,
        trainer=lambda **kwargs: trained.append(kwargs["project_dir"].name) or {
            "project": kwargs["project_dir"].name, "status": "hypothesis_not_confirmed",
        },
        probe=probe, progress=events.append, target_score=9.7,
        regression_projects=[], promote_config=True, write=False, policy=policy,
    )

    assert result["status"] == "completed"
    assert result["discovered_project_count"] == 5
    assert result["matching_project_count"] == 2
    assert trained == ["match_one", "match_two"]
    assert [plan["hypothesis_id"] for plan in plans] == [
        result["plan"]["hypothesis_id"], f'{result["plan"]["hypothesis_id"]}_r2',
    ]
    assert {"wrong_one", "wrong_two"} <= set(plans[1]["excluded_projects"])
    assert [plan["search_page_start"] for plan in plans] == [1, 3]
    stages = [event["stage"] for event in events]
    assert stages.count("holdout_discovery_round_started") == 2
    assert stages.count("holdout_probe_completed") == 5
    assert stages.count("holdout_training_completed") == 2
