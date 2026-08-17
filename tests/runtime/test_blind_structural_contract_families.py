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


def test_data_access_loaders_are_profiled_from_structure():
    cases = [
        (
            {
                "inferred_output_type": "pd.DataFrame",
                "observed_side_effects": ["database_read"],
                "raises": [],
            },
            "tabular_database_query_boundary",
        ),
        (
            {
                "inferred_output_type": "List[Account]",
                "observed_side_effects": ["filesystem_read"],
                "raises": ["DomainError"],
            },
            "filesystem_typed_collection_loader",
        ),
    ]
    for evidence, family in cases:
        evidence.update({"source_body_complete": True, "state_mutation": False})
        report = semantic_target_quality_report(
            "src/storage.py:get_records",
            ranked_candidates=["src/storage.py:get_records"],
            source_evidence=["src/storage.py:get_records"],
            structural_evidence=evidence,
            input_contract={"location": "DataLocation"},
            output_contract={"result": evidence["inferred_output_type"]},
            side_effect_contract={"declared": evidence["observed_side_effects"]},
        )
        assert report["contract_archetype_ids"] == [family]
        assert report["score"] >= 97


def test_bounded_runtime_render_and_query_contracts_are_profiled():
    cases = [
        (
            {"inferred_output_type": "TupleLike", "observed_side_effects": ["subprocess"]},
            "subprocess_tuple_query_boundary",
        ),
        (
            {"inferred_output_type": "VoidSideEffect", "observed_side_effects": ["observability"]},
            "observability_render_command",
        ),
    ]
    for evidence, family in cases:
        evidence.update({"source_body_complete": True, "state_mutation": False})
        report = semantic_target_quality_report(
            "src/runtime.py:render_or_query",
            ranked_candidates=["src/runtime.py:render_or_query"],
            source_evidence=["src/runtime.py:render_or_query"],
            structural_evidence=evidence,
            input_contract={"value": "RuntimeQueryInput"},
            output_contract={"result": evidence["inferred_output_type"]},
            side_effect_contract={"declared": evidence["observed_side_effects"]},
        )
        assert report["contract_archetype_ids"] == [family]
        assert report["score"] >= 97


def test_sequence_translation_and_filesystem_report_are_profiled_from_structure():
    cases = [
        (
            {
                "inferred_output_type": "Union[ArrayLike, SequenceLike]",
                "argument_usage_types": {"values": "IterableLike"},
                "observed_side_effects": [],
            },
            "sequence_array_translation_boundary",
        ),
        (
            {
                "inferred_output_type": "VoidSideEffect",
                "argument_usage_types": {"path": "PathLike"},
                "observed_side_effects": ["filesystem_read", "observability"],
            },
            "filesystem_read_observability_command",
        ),
    ]
    for evidence, family in cases:
        evidence.update({"source_body_complete": True, "state_mutation": False})
        report = semantic_target_quality_report(
            "src/domain.py:operate",
            ranked_candidates=["src/domain.py:operate"],
            source_evidence=["src/domain.py:operate"],
            structural_evidence=evidence,
            input_contract={"value": next(iter(evidence["argument_usage_types"].values()))},
            output_contract={"result": evidence["inferred_output_type"]},
            side_effect_contract={"declared": evidence["observed_side_effects"]},
        )
        assert report["contract_archetype_ids"] == [family]
        assert report["score"] >= 97
