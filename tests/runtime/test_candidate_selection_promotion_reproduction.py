from runtime.improvement_plugins import candidate_selection_admission as admission
from runtime.improvement_plugins.candidate_selection_refinement import (
    refine_preflight,
    refine_reproduction,
)


def _effect(score=9.7, signal="executable_callable"):
    return {
        "treatment": {
            "status": "ok",
            "project_min_score": score,
            "downstream_evidence": {"acceptance_signal": signal},
        },
    }


def test_holdout_reproduction_requires_untargeted_score_and_acceptance(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "runtime.improvement_plugins.candidate_selection_admission.evaluate_project",
        lambda *_args, **_kwargs: {
            "status": "ok",
            "project_min_score": 8.4,
            "downstream_evidence": {"acceptance_signal": "executable_callable"},
            "selected_extraction_candidate": "app.py:fallback",
        },
    )

    failure = admission._holdout_reproduction_failure(tmp_path, tmp_path, _effect())

    assert failure["expected_score"] == 9.7
    assert failure["actual_score"] == 8.4
    assert failure["selected_candidate"] == "app.py:fallback"


def test_holdout_reproduction_accepts_equal_ordinary_route(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "runtime.improvement_plugins.candidate_selection_admission.evaluate_project",
        lambda *_args, **_kwargs: {
            "status": "ok",
            "project_min_score": 9.7,
            "downstream_evidence": {"acceptance_signal": "executable_callable"},
        },
    )

    assert admission._holdout_reproduction_failure(tmp_path, tmp_path, _effect()) == {}


def test_reproduction_refinement_excludes_only_new_execution_cost():
    policy = {"structural_requirements": {"max_argument_count": 1}}
    effect = {"treatment": {"selected_candidate_quality": {"selection_evidence": {
        "ranking_reasons": ["execution cost requires reselection: instance_method_receiver"],
    }}}}
    reproduction = {"selected_candidate_quality": {"selection_evidence": {
        "ranking_reasons": [
            "execution cost requires reselection: instance_method_receiver, method_runtime_global_dependency"
        ],
    }}}

    refined = refine_reproduction(policy, effect, reproduction)

    assert refined["structural_requirements"]["forbidden_ranking_reason_tokens"] == [
        "method_runtime_global_dependency",
    ]
    assert refined["preflight_trigger_requirements"]["alternatives"][-1] == {
        "any_ranking_reason_tokens": ["method_runtime_global_dependency"],
    }


def test_reproduction_refinement_rejects_non_value_module_target():
    refined = refine_reproduction(
        {"structural_requirements": {"max_argument_count": 1}},
        {"treatment": {"selected_candidate_quality": {
            "structural_evidence": {"return_paths": 1},
        }}},
        {"selected_candidate_quality": {
            "structural_evidence": {
                "return_paths": 0,
                "output_inference_basis": "module_side_effect_execution",
            },
        }},
    )

    assert refined["structural_requirements"]["min_return_paths"] == 1
    assert refined["preflight_trigger_requirements"]["alternatives"][-1] == {
        "output_inference_basis": ["module_side_effect_execution"],
    }


def test_reproduction_refinement_uses_structured_dependency_status():
    refined = refine_reproduction(
        {"structural_requirements": {"max_argument_count": 1}},
        {"treatment": {"selected_candidate_quality": {"selection_evidence": {
            "dependency_readiness": {"status": "ready"},
        }}}},
        {"selected_candidate_quality": {"selection_evidence": {
            "dependency_readiness": {"status": "missing_external"},
        }}},
    )

    assert refined["structural_requirements"]["forbidden_dependency_status"] == [
        "missing_external",
    ]
    assert refined["preflight_trigger_requirements"]["alternatives"][-1] == {
        "dependency_status": ["missing_external"],
    }


def test_reproduction_refinement_does_not_treat_unknown_dependency_as_contrast():
    policy = {"structural_requirements": {"max_argument_count": 1}}
    refined = refine_reproduction(
        policy,
        {"treatment": {"selected_candidate_quality": {"selection_evidence": {}}}},
        {"selected_candidate_quality": {"selection_evidence": {
            "dependency_readiness": {"status": "ready"},
        }}},
    )

    assert refined == {}


def test_reproduction_refinement_rejects_state_only_zero_arity_method():
    refined = refine_reproduction(
        {"structural_requirements": {"max_argument_count": 1}},
        {"treatment": {"selected_candidate_quality": {
            "structural_evidence": {"argument_count": 1},
        }}},
        {"selected_candidate_quality": {
            "structural_evidence": {"argument_count": 0},
        }},
    )

    assert refined["structural_requirements"]["min_argument_count"] == 1
    assert refined["preflight_trigger_requirements"]["alternatives"][-1] == {
        "max_argument_count": 0,
    }


def test_reproduction_refinement_requires_source_bound_argument_shape():
    refined = refine_reproduction(
        {"structural_requirements": {"max_argument_count": 1}},
        {"treatment": {"selected_candidate_quality": {"structural_evidence": {
            "argument_count": 1,
            "argument_usage_types": {"center": "ArrayLike"},
        }}}},
        {"selected_candidate_quality": {"structural_evidence": {
            "argument_count": 1,
            "argument_usage_types": {},
        }}},
    )

    assert refined["structural_requirements"]["min_argument_usage_count"] == 1
    assert refined["preflight_trigger_requirements"]["alternatives"][-1] == {
        "max_argument_usage_count": 0,
    }


def test_regression_refinement_narrows_initial_dependency_trigger():
    policy = {
        "structural_requirements": {"max_argument_count": 1},
        "preflight_trigger_requirements": {"alternatives": [
            {"min_argument_count": 2},
            {"max_argument_count": 0},
        ]},
    }
    effect = {"control": {"selected_candidate_quality": {"selection_evidence": {
        "dependency_readiness": {"status": "missing_external"},
    }}}}
    regressions = [{"selected_candidate_quality": {"selection_evidence": {
        "dependency_readiness": {"status": "ready"},
    }}}]

    refined = refine_preflight(policy, effect, regressions)

    assert refined["preflight_trigger_requirements"]["common_requirements"]["dependency_status"] == [
        "missing_external",
    ]
    assert refined["preflight_trigger_requirements"]["alternatives"][0] == {
        "min_argument_count": 2,
    }
    assert refined["preflight_trigger_requirements"]["alternatives"][1] == {
        "max_argument_count": 0,
    }


def test_regression_refinement_uses_trigger_argument_shape():
    policy = {
        "structural_requirements": {"max_argument_count": 1},
        "preflight_trigger_requirements": {"min_argument_count": 2},
    }
    effect = {"control": {"selected_candidate_quality": {
        "structural_evidence": {"argument_count": 9},
    }}}
    regressions = [{"selected_candidate_quality": {
        "structural_evidence": {"argument_count": 2},
    }}]

    refined = refine_preflight(policy, effect, regressions)

    assert refined["preflight_trigger_requirements"]["common_requirements"]["min_argument_count"] == 9
