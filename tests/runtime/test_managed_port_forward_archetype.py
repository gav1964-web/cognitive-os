from runtime.contract_archetype_inference import contract_archetype_for_target
from runtime.target_quality import semantic_target_quality_report


def test_managed_port_forward_is_profiled_as_network_lifecycle_contract():
    target = "package/connection.py:forward_remote"

    contract = contract_archetype_for_target(target)
    quality = semantic_target_quality_report(
        target,
        ranked_candidates=[target],
        source_evidence=[target],
    )

    assert contract["contract_family"] == "managed_port_forward_boundary"
    assert contract["side_effect_policy"]["external_calls"].startswith("network transport")
    assert quality["status"] == "strong"
    assert quality["score"] >= 95


def test_json_schema_array_type_is_profiled_as_type_translation():
    target = "package/_json_schema.py:array_type"

    contract = contract_archetype_for_target(target)
    quality = semantic_target_quality_report(target, ranked_candidates=[target], source_evidence=[target])

    assert contract["contract_family"] == "schema_type_normalization_boundary"
    assert quality["status"] == "strong"
    assert quality["score"] >= 95
