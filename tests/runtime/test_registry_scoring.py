from __future__ import annotations

from runtime.registry import CapabilityRegistry


def test_registry_scoring_prefers_active_over_degraded(runtime_workspace):
    root = runtime_workspace
    registry = CapabilityRegistry(root)
    registry.reset_from_plugins()

    parse_title = registry.capabilities["parse_title"]
    candidates = registry.candidates_for_contract(
        input_schema=parse_title.input_schema,
        output_schema=parse_title.output_schema,
    )
    assert candidates[0].id in {"parse_title", "parse_title_fallback"}

    registry.mark_status("parse_title", "degraded")
    candidates = registry.candidates_for_contract(
        input_schema=parse_title.input_schema,
        output_schema=parse_title.output_schema,
    )

    assert candidates[0].id == "parse_title_fallback"
