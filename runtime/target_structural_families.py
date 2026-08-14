"""Config-backed structural contract family recognition."""

from __future__ import annotations

from typing import Any


def structural_contract_family(
    evidence: dict[str, Any] | None, side_effect_contract: dict[str, Any] | None = None
) -> str:
    facts = dict(evidence or {})
    decorators = {str(value).lower().rsplit(".", 1)[-1] for value in facts.get("decorators", [])}
    if decorators & {"route", "get", "post", "put", "patch", "delete"}:
        return "decorated_web_route_boundary"
    if "task" in decorators:
        return "decorated_background_task_boundary"
    usage = dict(facts.get("argument_usage_types") or {})
    output_type = str(facts.get("inferred_output_type") or "")
    observed = set(facts.get("observed_side_effects") or [])
    effects = set(dict(side_effect_contract or {}).get("declared") or [])
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
