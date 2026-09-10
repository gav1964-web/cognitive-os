from copy import deepcopy
import json

import pytest

from runtime.project_development_boundary_interpreter import (
    ProjectDevelopmentBoundaryKnowledgeError,
    evaluate_expression,
    interpret_boundary,
    load_boundary_profiles,
    load_exception_pickle_patterns,
    load_source_contrasts,
)


def _context(*, depth: int, append_sites: int, reason: str) -> dict:
    return {
        "feedback": {"reason": "no_unique_development_helper_extraction"},
        "source_facts": {
            "source_backed": True,
            "maximum_loop_depth": depth,
            "dict_append_sites": append_sites,
        },
        "reducer_attempts": [{
            "operation_kind": "extract_append_mapping_helper",
            "reason": reason,
        }],
    }


def test_interpreter_preserves_nested_boundary_characterization() -> None:
    profile = interpret_boundary(
        _context(depth=2, append_sites=1, reason="append_mapping_helper_pattern_not_proven")
    )

    assert profile["id"] == "nested_loop_mapping_boundary"
    assert profile["status"] == "staged"
    assert profile["hypothesis"]["confidence"] == 0.93
    assert profile["hypothesis"]["strategy"] == "characterize_nested_loop_boundary"


def test_interpreter_routes_simple_shape_to_bounded_research() -> None:
    profile = interpret_boundary(
        _context(depth=1, append_sites=1, reason="append_mapping_helper_pattern_not_proven")
    )

    assert profile["id"] == "unsupported_reducer_shape"
    assert profile["hypothesis"]["status"] == "research_more"


def test_interpreter_routes_missing_failure_reducer_to_bounded_research() -> None:
    context = _context(depth=0, append_sites=0, reason="not_attempted")
    context["feedback"]["reason"] = "no_verified_failure_reducer"

    profile = interpret_boundary(context)

    assert profile["id"] == "unsupported_reducer_shape"
    assert profile["hypothesis"]["status"] == "research_more"
    assert profile["evidence_state"]["minimum_additional_independent_projects"] == 0
    assert profile["evidence_state"]["minimum_additional_independent_contrasts_per_failure_kind"] == 2


def test_interpreter_stages_exception_pickle_reconstruction_boundary() -> None:
    context = {
        "feedback": {"reason": "no_verified_failure_reducer"},
        "source_facts": {
            "source_backed": True,
            "custom_exception_constructor": True,
            "base_exception_replays_constructor_parameters": False,
            "has_reduce_method": False,
        },
        "reducer_attempts": [],
    }

    profile = interpret_boundary(
        context,
        active_patterns={
            "schema_version": "exception_pickle_reconstruction_patterns.v1",
            "status": "absent",
        },
    )

    assert profile["id"] == "exception_pickle_reconstruction_boundary"
    assert profile["status"] == "staged"
    assert profile["hypothesis"]["status"] == "proposed"
    assert profile["hypothesis"]["confidence"] == 0.88
    assert profile["evidence_state"]["promotion_ready"] is False


def test_interpreter_overlays_active_exception_pickle_pattern() -> None:
    context = {
        "feedback": {"reason": "no_verified_failure_reducer"},
        "source_facts": {
            "source_backed": True,
            "custom_exception_constructor": True,
            "base_exception_replays_constructor_parameters": False,
            "has_reduce_method": False,
        },
        "reducer_attempts": [],
    }

    profile = interpret_boundary(context)

    assert profile["id"] == "exception_pickle_reconstruction_boundary"
    assert profile["status"] == "active"
    assert profile["hypothesis"]["confidence"] >= 0.97
    assert profile["active_kb_operator"]["status"] == "validated_active"
    assert profile["evidence_state"]["promotion_ready"] is True


def test_exception_pickle_pattern_catalog_loads_active_operator() -> None:
    catalog = load_exception_pickle_patterns()

    assert catalog["status"] == "active"
    assert catalog["operator"]["id"] == "preserve_exception_constructor_reconstruction"


def test_interpreter_fails_closed_to_fallback_without_source_evidence() -> None:
    context = _context(depth=2, append_sites=1, reason="append_mapping_helper_pattern_not_proven")
    context["source_facts"]["source_backed"] = False

    profile = interpret_boundary(context)

    assert profile["id"] == "unsupported_reducer_shape_fallback"
    assert profile["hypothesis"]["status"] == "knowledge_gap"


def test_unknown_predicate_operator_never_matches() -> None:
    assert evaluate_expression(
        {"source": "facts", "path": "depth", "operator": "execute", "value": 2},
        {"facts": {"depth": 2}},
    ) is False


def test_catalog_loader_rejects_unknown_operator(tmp_path) -> None:
    payload = deepcopy(load_boundary_profiles())
    payload["profiles"][0]["match"]["all"][0]["operator"] = "execute"
    path = tmp_path / "profiles.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ProjectDevelopmentBoundaryKnowledgeError):
        load_boundary_profiles(str(path))


def test_source_contrast_is_staged_and_cannot_promote_kb() -> None:
    contrast = load_source_contrasts()["contrasts"][0]

    assert contrast["status"] == "staged_evidence"
    assert contrast["provenance"]["kb_promotion_evidence"] is False


def test_exception_pickle_contrast_is_same_project_and_non_promotional() -> None:
    contrast = next(
        row for row in load_source_contrasts()["contrasts"]
        if row["contrast_id"] == "pytest_socket_direct_exception_args"
    )

    assert contrast["hypothesis_kind"] == "exception_pickle_reconstruction_boundary"
    assert contrast["provenance"]["same_project_contrast"] is True
    assert contrast["provenance"]["kb_promotion_evidence"] is False
