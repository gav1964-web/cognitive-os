from runtime.source_contract_semantics import infer_source_contract
from runtime.target_quality import semantic_target_quality_report


def test_nested_callable_return_is_inferred():
    evidence = infer_source_contract(
        {"snippet": "def factory(value, option):\n    def wrapped():\n        return value\n    return wrapped"}
    )

    assert evidence["inferred_output_type"] == "Callable"


def test_blind_corpus_structures_are_profiled_without_project_names():
    cases = [
        ({"inferred_output_type": "MappingLike", "argument_usage_types": {"source": "ProtocolLike"}}, "object_mapping_projection"),
        ({"inferred_output_type": "Callable", "argument_count": 2, "return_paths": 1}, "callable_decorator_factory"),
        ({"inferred_output_type": "str", "argument_count": 9, "return_paths": 1}, "parameterized_text_builder"),
        ({"inferred_output_type": "VoidSideEffect", "argument_usage_types": {"values": "MappingLike"}, "observed_side_effects": ["observability"]}, "mapping_observability_validation_command"),
    ]
    for evidence, family in cases:
        evidence.update({"source_body_complete": True, "state_mutation": False})
        report = semantic_target_quality_report(
            "src/domain.py:project", ranked_candidates=["src/domain.py:project"],
            source_evidence=["src/domain.py:project"], structural_evidence=evidence,
            input_contract={"value": "DomainInput"},
            output_contract={"result": evidence["inferred_output_type"]},
            side_effect_contract={"declared": evidence.get("observed_side_effects", [])},
        )
        assert report["contract_archetype_ids"] == [family]
        assert report["score"] >= 97
