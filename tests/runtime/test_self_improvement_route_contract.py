from runtime.semantic_target_profiles import temporary_semantic_profiles
from runtime.target_quality import semantic_target_quality_report
from runtime.technical_spec_builder import build_technical_spec


TARGET = "starlette_exporter/middleware.py:_flatten_routes"
STRUCTURAL = {
    "source_body_available": True,
    "source_body_complete": True,
    "argument_count": 1,
    "typed_argument_count": 1,
    "explicit_return_annotation": "Iterator[BaseRoute]",
    "inferred_output_type": "Iterator[BaseRoute]",
    "state_mutation": False,
    "return_paths": 1,
}
PROFILE = {
    "id": "training_route_tree_flatten_boundary_test",
    "contract_family": "route_tree_flatten_boundary",
    "symbols": ["_flatten_routes"],
    "path_contains_any": ["starlette_exporter/middleware.py"],
    "input_contract": {"routes": "RouteTree"},
    "output_contract": {"routes": "Iterator[MatchableRoute]"},
    "side_effect_policy": {"mutation_policy": "none"},
    "validation_gates": ["empty and compatibility branches terminate"],
    "failure_modes": ["route_cycle"],
    "benign_runtime_boundary": True,
    "score_bonus": 0,
    "ranking_bonus": 0,
}


def _report():
    return semantic_target_quality_report(
        TARGET,
        ranked_candidates=[TARGET],
        source_evidence=[TARGET],
        structural_evidence=STRUCTURAL,
        input_contract={"routes": "RouteTree"},
        output_contract={"routes": "Iterator[MatchableRoute]"},
        side_effect_contract={"declared": []},
    )


def test_typed_route_profile_resolves_runtime_boundary_conflict():
    control = _report()
    with temporary_semantic_profiles([PROFILE]):
        treatment = _report()

    assert control["score"] < 85
    assert treatment["status"] == "strong"
    assert treatment["score"] >= 97
    assert not any("needs semantic review" in reason for reason in treatment["reasons"])


def test_unprofiled_middleware_keeps_runtime_boundary_review():
    report = _report()

    assert report["status"] != "strong"
    assert any("needs semantic review" in reason for reason in report["reasons"])


def test_spec_materializes_profile_gates_and_failures():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Specify route traversal",
        "chosen_option": {"id": "bounded_route_traversal"},
        "spec_writer_brief": {
            "scope": ["Specify route-tree traversal."],
            "files_or_symbols": [TARGET],
            "first_slice": {"name": "route_traversal", "targets": [TARGET], "steps": ["Verify traversal."]},
        },
        "source_context": {
            TARGET: {
                "kind": "pure_transform",
                "signature": {"args": [{"name": "routes", "annotation": "Sequence[BaseRoute]"}], "returns": "Iterator[BaseRoute]"},
                "snippet": {"text": "def _flatten_routes(routes):\n    for route in routes:\n        yield route\n"},
            }
        },
    }
    with temporary_semantic_profiles([PROFILE]):
        spec = build_technical_spec(architecture_decision=adr)

    family_rows = [row for row in spec["acceptance_criteria"] if row.get("contract_family")]
    assert len(family_rows) == 2
    assert any(row.get("failure_mode") == "route_cycle" for row in family_rows)
    assert any(test.get("fixture_kind") == "contract_family_gate" for test in spec["verification_strategy"]["contract_tests"])
    assert any(test.get("failure_mode") == "route_cycle" for test in spec["verification_strategy"]["negative_tests"])
