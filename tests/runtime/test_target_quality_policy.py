from __future__ import annotations

import json

from runtime.role_spec_writer_ranking import name_and_contract_score
from runtime.target_structural_families import load_structural_family_rules, structural_contract_family
from runtime.target_quality import semantic_target_quality_report
from runtime.target_quality_policy import load_target_quality_policy


def test_target_quality_policy_loads_required_sections():
    policy = load_target_quality_policy()

    assert policy["schema_version"] == "target_quality_policy.v1"
    assert "target_quality" in policy
    assert "spec_writer_ranking" in policy
    assert policy["target_quality"]["suspicious_path_tokens"]
    assert policy["spec_writer_ranking"]["deterministic_shape_tokens"]


def test_structural_family_rules_are_kb_driven(tmp_path):
    path = tmp_path / "rules.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "structural_contract_family_rules.v1",
                "rules": [
                    {
                        "family_id": "custom_sequence_boundary",
                        "all": [{"field": "usage_types", "op": "contains", "value": "SequenceLike"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    family = structural_contract_family(
        {"argument_usage_types": {"items": "SequenceLike"}}, rules_path=str(path)
    )

    assert family == "custom_sequence_boundary"


def test_structural_family_rules_reject_unknown_operator(tmp_path):
    path = tmp_path / "rules.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "structural_contract_family_rules.v1",
                "rules": [{"family_id": "unsafe", "all": [{"field": "value", "op": "eval"}]}],
            }
        ),
        encoding="utf-8",
    )

    try:
        load_structural_family_rules(str(path))
    except ValueError as exc:
        assert "invalid structural condition" in str(exc)
    else:
        raise AssertionError("unknown operators must be rejected")


def test_target_quality_policy_drives_quality_and_ranking_rules():
    weak = semantic_target_quality_report(
        "pkg/utils/helper.py:version",
        ranked_candidates=["pkg/utils/helper.py:version"],
        source_evidence=["pkg/utils/helper.py:version"],
    )
    strong = semantic_target_quality_report(
        "pkg/parser.py:parse_payload",
        ranked_candidates=["pkg/parser.py:parse_payload"],
        source_evidence=["pkg/parser.py:parse_payload"],
    )
    score, reasons = name_and_contract_score(
        "pkg/parser.py:parse_payload",
        {"args": [{"name": "payload", "annotation": "dict"}], "returns": "ParsedPayload"},
        [],
    )

    assert weak["status"] in {"suspicious", "poor"}
    assert strong["status"] == "strong"
    assert score > 0
    assert "deterministic parser" in " ".join(reasons)


def test_validate_url_contract_is_not_treated_as_trivial_url_accessor():
    target = "package/utils.py:_validate_repository_url"

    report = semantic_target_quality_report(
        target,
        ranked_candidates=[target],
        source_evidence=[target],
        selection_reason="deterministic parser/normalizer/validator shape",
    )

    assert report["status"] == "strong"
    assert report["score"] >= 95
    assert not any("trivial accessor" in reason for reason in report["reasons"])


def test_complete_sdk_operation_is_not_rejected_by_filename_suffix():
    target = "sdk/accounting_api.py:create_attachment_by_file_name"
    structural = {
        "source_body_complete": True,
        "argument_count": 8,
        "return_paths": 1,
        "raises": ["ValueError"],
    }

    operation = semantic_target_quality_report(
        target,
        ranked_candidates=[target],
        source_evidence=[target],
        selection_reason="deterministic parser/normalizer/validator shape",
        structural_evidence=structural,
    )
    accessor = semantic_target_quality_report(
        "sdk/model.py:get_name",
        ranked_candidates=["sdk/model.py:get_name"],
        source_evidence=["sdk/model.py:get_name"],
        structural_evidence={"source_body_complete": True, "argument_count": 0, "return_paths": 1, "raises": []},
    )

    assert operation["status"] in {"acceptable", "strong"}
    assert "trivial accessor/value helper is weak as first architectural slice" not in operation["reasons"]
    assert accessor["status"] != "strong"


def test_profiled_version_operation_is_not_treated_as_support_version_helper():
    report = semantic_target_quality_report(
        "django_redis/client/default.py:incr_version",
        ranked_candidates=["django_redis/client/default.py:incr_version"],
        source_evidence=["django_redis/client/default.py:incr_version"],
    )

    assert report["status"] == "strong"
    assert report["score"] >= 95
    assert not any("support/utility target: version" in reason for reason in report["reasons"])


def test_command_entrypoint_profile_reaches_excellent_score():
    report = semantic_target_quality_report(
        "src/trustme/_cli.py:main",
        ranked_candidates=["src/trustme/_cli.py:main"],
        source_evidence=["src/trustme/_cli.py:main"],
    )

    assert report["status"] == "strong"
    assert report["score"] >= 98
    assert report["semantic_profile_ids"] == ["command_entrypoint_invocation_boundary"]


def test_profiled_pytest_decorator_is_not_treated_as_utility_noise():
    target = "src/pytest_bdd/scenario.py:_get_scenario_decorator"

    report = semantic_target_quality_report(
        target,
        ranked_candidates=[target],
        source_evidence=[target],
    )

    assert report["status"] == "strong"
    assert report["score"] >= 95
    assert report["contract_archetype_ids"] == ["pytest_fixture_or_decorator_registration"]
    assert not any("support/utility target: decorator" in reason for reason in report["reasons"])


def test_source_proven_persistence_command_gets_structural_family():
    target = "database/custom_graph.py:add_value"
    report = semantic_target_quality_report(
        target,
        ranked_candidates=[target],
        source_evidence=[target],
        structural_evidence={
            "source_body_complete": True,
            "inferred_output_type": "VoidSideEffect",
            "observed_side_effects": ["database"],
        },
        input_contract={"session": "PersistenceSession", "value": "RecordInput"},
        output_contract={"result": "VoidSideEffect"},
        side_effect_contract={"declared": ["database"]},
    )

    assert report["profiled_contract_family"] is True
    assert report["contract_archetype_ids"] == ["persistence_append_command"]
    assert report["score"] >= 97


def test_source_proven_common_contract_shapes_get_structural_families():
    cases = [
        ({"source_body_complete": True, "async_callable": True, "inferred_output_type": "VoidSideEffect", "argument_usage_types": {"events": "IterableLike"}, "state_mutation": False}, {"declared": []}, "async_batch_processing_boundary"),
        ({"source_body_complete": True, "inferred_output_type": "VoidSideEffect", "argument_usage_types": {"mapping": "MappingLike"}, "state_mutation": True}, {"declared": ["memory_state"]}, "ordered_mapping_mutation_boundary"),
        ({"source_body_complete": True, "inferred_output_type": "MappingLike", "observed_side_effects": ["database"], "state_mutation": False}, {"declared": ["database"]}, "database_read_mapping_boundary"),
        ({"source_body_complete": True, "inferred_output_type": "ResponseLike", "decorators": ["action"]}, {"declared": ["database"]}, "decorated_web_route_boundary"),
    ]
    for evidence, effects, family in cases:
        report = semantic_target_quality_report(
            "src/domain.py:process", ranked_candidates=["src/domain.py:process"],
            source_evidence=["src/domain.py:process"], structural_evidence=evidence,
            input_contract={"value": "DomainInput"}, output_contract={"result": evidence["inferred_output_type"]},
            side_effect_contract=effects,
        )
        assert report["contract_archetype_ids"] == [family]


def test_additional_source_proven_contract_shapes_get_structural_families():
    cases = [
        (
            {"source_body_complete": True, "inferred_output_type": "VoidSideEffect", "argument_usage_types": {"rows": "IterableLike"}, "observed_side_effects": ["observability"], "state_mutation": False},
            "iterable_observability_report_command",
        ),
        (
            {"source_body_complete": True, "inferred_output_type": "Union[ArrayLike, TupleLike]", "return_paths": 2, "observed_side_effects": [], "state_mutation": False},
            "multi_shape_prediction_boundary",
        ),
        (
            {"source_body_complete": True, "inferred_output_type": "ResponseLike", "decorators": ["app.errorhandler"]},
            "decorated_web_error_boundary",
        ),
        (
            {"source_body_complete": True, "inferred_output_type": "SetLike", "argument_usage_types": {"context": "ProtocolLike"}, "observed_side_effects": [], "state_mutation": False},
            "protocol_operator_result_boundary",
        ),
    ]
    for evidence, family in cases:
        report = semantic_target_quality_report(
            "src/domain.py:process",
            ranked_candidates=["src/domain.py:process"],
            source_evidence=["src/domain.py:process"],
            structural_evidence=evidence,
            input_contract={"value": "DomainInput"},
            output_contract={"result": evidence["inferred_output_type"]},
            side_effect_contract={"declared": evidence.get("observed_side_effects", [])},
        )
        assert report["contract_archetype_ids"] == [family]
        assert report["score"] >= 97


def test_decorated_identity_loader_combines_structure_and_ranking_evidence():
    target = "app/models.py:load_user"
    report = semantic_target_quality_report(
        target,
        ranked_candidates=[target],
        source_evidence=[target],
        selection_reason="pure transform with deterministic identity lookup",
        structural_evidence={
            "source_body_complete": True,
            "inferred_output_type": "InferredOutput",
            "decorators": ["login.user_loader"],
            "state_mutation": False,
        },
        input_contract={"identity": "IdentityKey"},
        output_contract={"principal": "InferredOutput"},
        side_effect_contract={"declared": []},
    )

    assert report["contract_archetype_ids"] == ["decorated_identity_loader_boundary"]
    assert report["score"] >= 97


def test_mapping_report_command_requires_observability_only_boundary():
    target = "fingerprint.py:identify_fingerprint"
    structural = {
        "source_body_complete": True,
        "argument_count": 1,
        "argument_usage_types": {"fingerprint": "MappingLike"},
        "inferred_output_type": "VoidSideEffect",
        "state_mutation": False,
    }
    report = semantic_target_quality_report(
        target,
        ranked_candidates=[target],
        source_evidence=[target],
        structural_evidence=structural,
        input_contract={"fingerprint": "MappingLike"},
        output_contract={"result": "VoidSideEffect"},
        side_effect_contract={"declared": ["observability"]},
    )
    network = semantic_target_quality_report(
        target,
        ranked_candidates=[target],
        source_evidence=[target],
        structural_evidence=structural,
        input_contract={"fingerprint": "MappingLike"},
        output_contract={"result": "VoidSideEffect"},
        side_effect_contract={"declared": ["network", "observability"]},
    )

    assert report["contract_archetype_ids"] == ["mapping_observability_report_command"]
    assert report["score"] >= 97
    assert network["contract_archetype_ids"] == []


def test_external_authorization_policy_requires_async_network_boolean_contract():
    target = "chat.py:verify_user_for_room"
    report = semantic_target_quality_report(
        target,
        ranked_candidates=[target],
        source_evidence=[target],
        structural_evidence={
            "source_body_complete": True,
            "async_callable": True,
            "return_paths": 2,
            "inferred_output_type": "bool",
            "observed_side_effects": ["network", "observability"],
            "state_mutation": False,
        },
        input_contract={"chat_info": "AuthorizationContext"},
        output_contract={"authorized": "bool"},
        side_effect_contract={"declared": ["filesystem", "network", "observability"]},
    )

    assert report["contract_archetype_ids"] == ["external_authorization_policy"]
    assert report["score"] >= 97


def test_response_ordering_and_cached_analysis_structures_are_bounded_families():
    ordering = semantic_target_quality_report(
        "sdk/database.py:sort",
        ranked_candidates=["sdk/database.py:sort"],
        source_evidence=["sdk/database.py:sort"],
        structural_evidence={
            "source_body_complete": True,
            "inferred_output_type": "ResponseLike",
            "argument_usage_types": {"origin": "ProtocolLike", "by_key": "KeyLike"},
        },
        input_contract={"origin": "ProtocolLike", "by_key": "KeyLike"},
        output_contract={"result": "ResponseLike"},
        side_effect_contract={"declared": []},
    )
    cached = semantic_target_quality_report(
        "analysis/pipeline.py:propagate",
        ranked_candidates=["analysis/pipeline.py:propagate"],
        source_evidence=["analysis/pipeline.py:propagate"],
        structural_evidence={
            "source_body_complete": True,
            "return_paths": 2,
            "inferred_output_type": "Union[SequenceLike, TupleLike]",
            "argument_usage_types": {"left": "PathLike", "right": "PathLike", "signals": "MappingLike"},
            "observed_side_effects": ["filesystem_read", "observability"],
        },
        input_contract={"left": "PathLike", "right": "PathLike", "signals": "MappingLike"},
        output_contract={"result": "Union[SequenceLike, TupleLike]"},
        side_effect_contract={"declared": ["filesystem_read", "observability"]},
    )

    assert ordering["contract_archetype_ids"] == ["response_collection_ordering_transform"]
    assert ordering["score"] >= 97
    assert cached["contract_archetype_ids"] == ["cached_analysis_transform"]
    assert cached["score"] >= 97
