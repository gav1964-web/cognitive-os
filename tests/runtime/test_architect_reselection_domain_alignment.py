from runtime.architect_first_slice_reselection import (
    _domain_aligned_sources,
    _expanded_candidate_sources,
    _semantic_threshold_satisfied,
    _viable_candidates,
)
from runtime.architect_candidate_quality import contract_quality


def test_scientific_reselection_excludes_unrelated_operational_support():
    sources = [
        "pkg/system/logger.py:init",
        "pkg/math/derivative.py:derivative_stack",
        "pkg/solver.py:solve",
    ]
    architecture_decision = {
        "first_slice_contract": {"knowledge_rule": "scientific_compute_library"}
    }
    policy = {
        "domain_candidate_required_any": {
            "scientific_compute_library": ["math/", "derivative", "solve"]
        }
    }

    assert _domain_aligned_sources(sources, architecture_decision, policy) == [
        "pkg/math/derivative.py:derivative_stack",
        "pkg/solver.py:solve",
    ]


def test_unprofiled_reselection_preserves_candidate_window():
    sources = ["pkg/system/logger.py:init", "pkg/core.py:normalize"]

    assert _domain_aligned_sources(sources, {}, {}) == sources


def test_expanded_reselection_excludes_root_example_scripts():
    report = {
        "answers": {
            "3_capabilities": {
                "pure_transforms": [
                    {"source": "example_menu.py:main_loop"},
                    {"source": "pkg/core.py:normalize"},
                ]
            }
        }
    }
    policy = {"candidate_sources": ["pure_transforms"], "expanded_candidate_limit": 8}

    assert _expanded_candidate_sources(report, {}, policy) == ["pkg/core.py:normalize"]


def test_expanded_reselection_can_use_analyzer_callable_inventory():
    report = {"reselection_candidate_inventory": ["pkg/features.py:extract_features"]}
    policy = {"candidate_sources": ["project_callable_inventory"], "expanded_candidate_limit": 8}

    assert _expanded_candidate_sources(report, {}, policy) == ["pkg/features.py:extract_features"]


def test_expanded_reselection_can_use_analyzer_analysis_tasks():
    report = {"analysis_tasks": {"tasks": [
        {"target": "pkg/core.py:normalize", "type": "DRAFT_PIPELINE_CAPABILITY"},
        {"target": "README.md", "type": "REVIEW_DOCUMENTATION"},
    ]}}
    policy = {"candidate_sources": ["analysis_tasks"], "expanded_candidate_limit": 8}

    assert _expanded_candidate_sources(report, {}, policy) == ["pkg/core.py:normalize"]


def test_reselection_does_not_spend_iteration_on_candidate_below_spec_threshold():
    source = "pkg/core.py:transform"
    context = {
        source: {
            "node_kind": "function",
            "snippet": {
                "text": "def transform(value): return value",
                "target_binding": "function_symbol",
                "signature": {"args": [{"name": "value"}]},
                "structural_contract": {"source_body_complete": True, "inferred_output_type": "InferredOutput"},
            },
            "dependency_readiness": {"status": "ready"},
        }
    }

    selected, viable = _viable_candidates([source], context, {}, limit=8, minimum_semantic_score=95)

    assert viable and viable[0]["semantic_score"] < 95
    assert selected == []


def test_learned_policy_can_admit_deferred_candidate(monkeypatch):
    source = "pkg/core.py:normalize"
    context = {source: {
        "node_kind": "function",
        "dependency_readiness": {"status": "ready"},
        "snippet": {
            "text": "def normalize(value): return value",
            "target_binding": "method_symbol",
            "signature": {"args": [{"name": "value"}]},
            "structural_contract": {
                "return_paths": 1,
                "argument_usage_types": {"value": "ScalarLike"},
            },
        },
    }}
    monkeypatch.setattr(
        "runtime.architect_first_slice_reselection.apply_selection_policies",
        lambda rows, _request: [{**rows[0], "selection_policy_ids": ["learned"]}],
    )

    selected, _ranked = _viable_candidates(
        [source], context, {}, limit=1, selection_request={"trigger": "executable_acceptance_rejected"},
    )

    assert selected == [source]


def test_reselection_accepts_strong_candidate_at_semantic_policy_floor():
    assert _semantic_threshold_satisfied(
        {"semantic_status": "strong", "semantic_score": 95}, None, 95
    )
    assert not _semantic_threshold_satisfied(
        {"semantic_status": "strong", "semantic_score": 94}, None, 95
    )


def test_reselection_accepts_only_strong_configured_viability_override():
    matched = [{"rule_id": "static_time_format_boundary"}]

    assert _semantic_threshold_satisfied(
        {"semantic_status": "strong", "semantic_score": 89, "matched_rules": matched},
        None,
        95,
    )
    assert not _semantic_threshold_satisfied(
        {"semantic_status": "suspicious", "semantic_score": 89, "matched_rules": matched},
        None,
        95,
    )


def test_architect_quality_preserves_analyzer_pure_transform_evidence():
    source = "pkg/math.py:normalize"
    context = {
        "kind": "pure_transform",
        "snippet": {
            "signature": {"args": [{"name": "value", "annotation": "str"}]},
            "structural_contract": {
                "source_body_complete": True,
                "inferred_output_type": "str",
                "state_mutation": False,
            },
        },
    }

    quality = contract_quality(source, context, [source])

    assert quality["semantic_score"] >= 97


def test_reselection_prefers_strong_method_contract_over_weak_convenience_function():
    function = "pkg/logger.py:critical"
    formatter = "pkg/formatters.py:EventFormatter.formatMessage"
    context = {
        function: {
            "node_kind": "function",
            "snippet": {
                "text": "def critical(message): logger.critical(message)",
                "target_binding": "function_symbol",
                "structural_contract": {
                    "source_body_complete": True,
                    "inferred_output_type": "VoidSideEffect",
                    "observed_side_effects": ["observability"],
                },
            },
            "dependency_readiness": {"status": "ready"},
        },
        formatter: {
            "node_kind": "function",
            "snippet": {
                "text": "def formatMessage(self, record): return self._style.format(record)",
                "target_binding": "method_symbol",
                "owner_class": "EventFormatter",
                "structural_contract": {
                    "source_body_complete": True,
                    "argument_count": 1,
                    "typed_argument_count": 1,
                    "inferred_output_type": "str",
                    "return_paths": 1,
                },
            },
            "dependency_readiness": {"status": "ready"},
        },
    }

    selected, evidence = _viable_candidates([function, formatter], context, {}, limit=2)

    assert selected[0] == formatter
    assert evidence[0]["semantic_score"] >= evidence[1]["semantic_score"]
