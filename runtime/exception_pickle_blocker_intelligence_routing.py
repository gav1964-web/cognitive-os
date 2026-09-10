"""Next-operator lane routing for exception-pickle blocker intelligence."""

from __future__ import annotations

from collections import Counter
from typing import Any


def _classify_lane(
    *,
    blocker_kind: str,
    key: str,
    class_name: str = "",
    missing_inputs: list[str],
    unsupported_inputs: list[str],
    semantic_replay_error: str = "",
    source_facts: dict[str, Any],
    admitted_object_contracts: dict[str, dict[str, Any]],
    materializer_behavior_readmission_delta: bool = False,
    self_reference_args_readmission_delta: bool = False,
    static_patch_readmission_supported: bool = False,
    static_patch_supported: bool = False,
    dependency_light: bool = False,
) -> str:
    fact_tags = set(source_facts.get("fact_tags") or [])
    if blocker_kind == "semantic_sample_shape_unsupported":
        if key in admitted_object_contracts:
            return "admitted_object_contract_replay_frontier"
        if not unsupported_inputs and static_patch_readmission_supported:
            return "sample_supported_readmission_frontier"
        if not unsupported_inputs and static_patch_supported and not dependency_light:
            return "import_dependency_isolation_candidate"
        if not unsupported_inputs:
            return "patch_shape_operator_candidate"
        if "parameter_method_call" in fact_tags:
            return "bounded_method_materializer_candidate"
        if fact_tags & {"attribute_access", "mapping_access", "iterable_usage", "string_rendering"}:
            return "source_backed_object_materializer_candidate"
        return "opaque_object_contract_research"
    if blocker_kind == "constructor_inputs_not_replayable":
        if missing_inputs and fact_tags & {"derived_self_assignment", "direct_self_assignment"}:
            return "self_assignment_extraction_candidate"
        if missing_inputs and "base_exception_argument_transform" in fact_tags:
            return "derived_constructor_value_reconstruction_candidate"
        return "constructor_state_contract_research"
    if blocker_kind in {"semantic_replay_dependency_unavailable", "semantic_replay_import_failed"}:
        return "import_dependency_isolation_candidate"
    if blocker_kind == "semantic_replay_behavior_mismatch":
        if "attribute_base_class_definition" in fact_tags:
            return "import_dependency_isolation_candidate"
        if (
            _is_target_class_missing_attribute_error(semantic_replay_error, class_name=class_name)
            or "target_self_attribute_read_without_assignment" in fact_tags
        ):
            return "class_state_contract_research"
        if unsupported_inputs:
            return "semantic_materializer_behavior_candidate"
        return "semantic_behavior_contrast_research"
    if blocker_kind == "static_patch_shape_unsupported":
        if static_patch_readmission_supported:
            return "sample_supported_readmission_frontier"
        return "patch_shape_operator_candidate"
    if blocker_kind == "sandbox_copy_failed":
        return "corpus_filesystem_hygiene"
    if blocker_kind == "constructor_input_count_out_of_policy":
        return "wide_constructor_deferred"
    return "unknown_blocker_research"


def _recommended_sequence(counter: Counter[str]) -> list[dict[str, Any]]:
    priorities = {
        "admitted_object_contract_replay_frontier": 100,
        "sample_supported_readmission_frontier": 95,
        "source_backed_object_materializer_candidate": 90,
        "bounded_method_materializer_candidate": 85,
        "import_dependency_isolation_candidate": 75,
        "self_assignment_extraction_candidate": 70,
        "derived_constructor_value_reconstruction_candidate": 65,
        "patch_shape_operator_candidate": 55,
        "semantic_materializer_behavior_candidate": 50,
        "class_state_contract_research": 45,
        "constructor_state_contract_research": 35,
        "opaque_object_contract_research": 30,
        "semantic_behavior_contrast_research": 25,
        "corpus_filesystem_hygiene": 20,
        "wide_constructor_deferred": 10,
        "unknown_blocker_research": 5,
    }
    items = sorted(
        counter.items(),
        key=lambda item: (-priorities.get(item[0], 0), -item[1], item[0]),
    )
    return [
        {
            "lane": lane,
            "case_count": count,
            "priority": priorities.get(lane, 0),
            "next_action": _next_action(lane),
        }
        for lane, count in items
    ]


def _next_action(lane: str) -> str:
    actions = {
        "admitted_object_contract_replay_frontier": (
            "run bounded active-application saturation with admitted object contracts"
        ),
        "sample_supported_readmission_frontier": (
            "rerun old semantic sample blockers that current materializers now support"
        ),
        "source_backed_object_materializer_candidate": (
            "promote more deterministic source-backed samples through audit/admission"
        ),
        "bounded_method_materializer_candidate": (
            "extend method-object materializer only for zero-arg source-backed return profiles"
        ),
        "import_dependency_isolation_candidate": (
            "harden direct-file replay and target-scoped import stubs without broad module mocking"
        ),
        "self_assignment_extraction_candidate": (
            "teach audit to recognize missed self assignments and aliases"
        ),
        "derived_constructor_value_reconstruction_candidate": (
            "research replay of source-backed derived constructor values without widening active operator"
        ),
        "patch_shape_operator_candidate": (
            "add a separate patch-shape operator for classes current reducer cannot edit"
        ),
        "class_state_contract_research": (
            "research constructor reads of target class attributes before readmission"
        ),
    }
    return actions.get(lane, "collect source evidence and keep source apply forbidden")


def _is_target_class_missing_attribute_error(error_text: str, *, class_name: str) -> bool:
    if not error_text or not class_name:
        return False
    marker = f"AttributeError: '{class_name}' object has no attribute "
    return marker in error_text
