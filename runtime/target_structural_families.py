"""Config-backed structural contract family recognition."""

from __future__ import annotations

from typing import Any


def structural_contract_family(
    evidence: dict[str, Any] | None, side_effect_contract: dict[str, Any] | None = None
) -> str:
    facts = dict(evidence or {})
    decorators = {str(value).lower().rsplit(".", 1)[-1] for value in facts.get("decorators", [])}
    if decorators & {"route", "action", "get", "post", "put", "patch", "delete"}:
        return "decorated_web_route_boundary"
    if "errorhandler" in decorators:
        return "decorated_web_error_boundary"
    if "task" in decorators:
        return "decorated_background_task_boundary"
    usage = dict(facts.get("argument_usage_types") or {})
    output_type = str(facts.get("inferred_output_type") or "")
    observed = set(facts.get("observed_side_effects") or [])
    effects = set(dict(side_effect_contract or {}).get("declared") or [])
    if (
        output_type == "VoidSideEffect" and facts.get("async_callable")
        and "IterableLike" in set(usage.values()) and facts.get("source_body_complete")
        and not facts.get("state_mutation")
    ):
        return "async_batch_processing_boundary"
    if (
        output_type == "VoidSideEffect" and "MappingLike" in set(usage.values())
        and "memory_state" in effects and facts.get("source_body_complete")
        and facts.get("state_mutation")
    ):
        return "ordered_mapping_mutation_boundary"
    if (
        output_type == "MappingLike" and "database" in set(facts.get("observed_side_effects") or [])
        and facts.get("source_body_complete") and not facts.get("state_mutation")
    ):
        return "database_read_mapping_boundary"
    if output_type.lower().startswith("iterator[") and usage.get("routes") == "IterableLike" and facts.get("yield_paths"):
        return "route_tree_flatten_boundary"
    if output_type == "VoidSideEffect" and "database" in observed and facts.get("source_body_complete"):
        return "persistence_append_command"
    if facts.get("file_extension_policy") and output_type == "bool":
        return "file_extension_admission_policy"
    usage_types = set(usage.values())
    if output_type == "ResponseLike" and {"KeyLike", "ProtocolLike"} <= usage_types and not observed and facts.get("source_body_complete"):
        return "response_collection_ordering_transform"
    if (
        output_type.startswith("Union[")
        and sum(value == "PathLike" for value in usage.values()) >= 2
        and "MappingLike" in usage_types
        and "filesystem_read" in observed
        and observed <= {"filesystem_read", "observability"}
        and int(facts.get("return_paths") or 0) >= 2
        and facts.get("source_body_complete")
    ):
        return "cached_analysis_transform"
    if (
        output_type == "VoidSideEffect"
        and int(facts.get("argument_count") or 0) == 1
        and "MappingLike" in usage_types
        and effects == {"observability"}
        and facts.get("source_body_complete")
        and not facts.get("state_mutation")
    ):
        return "mapping_observability_report_command"
    if (
        output_type == "VoidSideEffect"
        and "IterableLike" in usage_types
        and observed == {"observability"}
        and facts.get("source_body_complete")
        and not facts.get("state_mutation")
    ):
        return "iterable_observability_report_command"
    if (
        output_type.startswith("Union[")
        and {"ArrayLike", "TupleLike"} <= {part.strip() for part in output_type[6:-1].split(",")}
        and int(facts.get("return_paths") or 0) >= 2
        and facts.get("source_body_complete")
        and not observed
        and not facts.get("state_mutation")
    ):
        return "multi_shape_prediction_boundary"
    if (
        output_type == "SetLike"
        and "ProtocolLike" in usage_types
        and facts.get("source_body_complete")
        and not observed
        and not facts.get("state_mutation")
    ):
        return "protocol_operator_result_boundary"
    if (
        output_type == "bool"
        and facts.get("async_callable")
        and int(facts.get("return_paths") or 0) >= 2
        and "network" in effects
        and "network" in observed
        and observed <= {"network", "observability"}
        and facts.get("source_body_complete")
        and not facts.get("state_mutation")
    ):
        return "external_authorization_policy"
    return ""
