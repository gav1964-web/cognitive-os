"""Infer bounded acceptance samples from local AST constraints."""

from __future__ import annotations

from .executable_acceptance_attribute_samples import add_parameter_attribute_samples
from .executable_acceptance_file_samples import add_delimited_file_samples
from .executable_acceptance_literal_buffers import add_literal_buffer_samples
from .executable_acceptance_parameter_strategies import add_parameter_strategy_samples
from .executable_acceptance_protocol_samples import (
    add_iterated_literal_domain_samples,
    add_mapping_protocol_samples,
    add_parameter_method_samples,
)
from .executable_acceptance_qualified_samples import add_qualified_call_samples
from .executable_acceptance_structural_callables import (
    _guarded_optional_callable_parameters,
    _parameter_callable_samples,
    _parameter_unpack_samples,
    _split_unpack_samples,
)
from .executable_acceptance_structural_common import (
    Candidates,
    FunctionNode,
    _comparison_sample,
    _direct_parameter,
    _literal,
    _priority,
    _safe_scalar,
    _settings,
)
from .executable_acceptance_structural_domains import (
    _allowed_collection_domains,
    _format_hint,
    _importable_module_paths,
    _keyword_payload_keys,
    _literal_membership_domains,
    _module_literal_collections,
    _parameter_aliases,
    _required_mapping_keys,
    _validation_format_hints,
)
from .executable_acceptance_structural_shapes import (
    _array_axis_samples,
    _comparison,
    _conversion,
    _dynamic_type_checks,
    _length_constraint,
    _length_parameter,
    _numeric_sequence,
    _positive_cube,
    _root_parameter,
    _strptime,
    _string_sequence_parameters,
    _tensor_window_contract_samples,
    _unpack_count,
    add_shape_structural_samples,
)


def collect_structural_samples(
    tree: object, node: FunctionNode, parameters: set[str], candidates: Candidates
) -> None:
    _dynamic_type_checks(node, parameters, candidates)
    add_iterated_literal_domain_samples(node, parameters, candidates, priority=_priority("iterated_literal_domain"))
    buffer_policy = dict(_settings().get("literal_buffer_methods") or {})
    add_literal_buffer_samples(
        node,
        parameters,
        candidates,
        priority=_priority("literal_buffer_method"),
        methods=dict(buffer_policy.get("positions") or {}),
        minimum_length=min(
            int(buffer_policy.get("minimum_length") or 0),
            int(_settings().get("maximum_inferred_length") or 0),
        ),
    )
    add_qualified_call_samples(
        node, parameters, candidates,
        priority=_priority("qualified_call_argument"),
        samples=dict(_settings().get("qualified_call_argument_samples") or {}),
    )
    add_shape_structural_samples(node, parameters, candidates)
    _required_mapping_keys(node, parameters, candidates)
    _literal_membership_domains(node, parameters, candidates)
    _parameter_unpack_samples(node, parameters, candidates)
    add_parameter_strategy_samples(
        node,
        parameters,
        candidates,
        policy=dict(_settings().get("parameter_strategies") or {}),
        priorities=dict(_settings().get("priorities") or {}),
    )
    _parameter_callable_samples(node, parameters, candidates)
    _split_unpack_samples(node, parameters, candidates)
    _keyword_payload_keys(node, candidates)
    _validation_format_hints(node, parameters, candidates)
    add_parameter_attribute_samples(
        tree, node, parameters, candidates,
        priority=_priority("parameter_attributes"),
        unpack_priority=_priority("parameter_unpack"),
        unpack_policy=dict(_settings().get("unpack_samples") or {}),
        attribute_policy=dict(_settings().get("attribute_samples") or {}),
    )
    add_parameter_method_samples(
        node,
        parameters,
        candidates,
        priority=_priority("parameter_attributes"),
        prefixes=tuple(str(item) for item in _settings().get("protocol_method_prefixes", [])),
    )
    add_mapping_protocol_samples(
        node,
        parameters,
        candidates,
        priority=_priority("parameter_attributes"),
        methods={str(item) for item in _settings().get("mapping_protocol_methods", [])},
        sample=dict(_settings().get("mapping_protocol_sample") or {}),
    )
    add_delimited_file_samples(
        node, parameters, candidates, priority=_priority("importable_module_path")
    )
    _importable_module_paths(node, parameters, candidates)
    _allowed_collection_domains(tree, node, parameters, candidates)


__all__ = ["Candidates", "FunctionNode", "collect_structural_samples"]
