from __future__ import annotations

from tests.runtime.target_quality_policy_helpers import *

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


def test_non_implementation_and_example_targets_are_not_strong_first_slices():
    abstract = semantic_target_quality_report(
        "pkg/hooks.py:Hook.process",
        structural_evidence={"source_body_complete": True, "decorators": ["abstractmethod"]},
    )
    example = semantic_target_quality_report(
        "pkg/progress.py:example1",
        structural_evidence={"source_body_complete": True},
    )
    stub = semantic_target_quality_report(
        "pkg/hooks.py:Hook.value",
        structural_evidence={
            "source_body_complete": True, "raises": ["NotImplementedError"], "return_paths": 0,
        },
    )

    assert abstract["status"] in {"suspicious", "poor"}
    assert example["status"] != "strong"
    assert stub["status"] in {"suspicious", "poor"}


def test_zero_argument_receiver_state_accessor_is_not_a_strong_first_slice():
    report = semantic_target_quality_report(
        "common/env_iroko.py:neighbors",
        ranked_candidates=["common/env_iroko.py:neighbors"],
        source_evidence=["common/env_iroko.py:neighbors"],
        selection_reason="pure transform candidate",
        structural_evidence={
            "source_body_complete": True,
            "owner_class": "Env",
            "argument_count": 0,
            "called_operations": [],
            "observed_side_effects": [],
            "state_mutation": False,
            "return_paths": 1,
        },
    )

    assert report["status"] != "strong"
    assert report["score"] <= 84
    assert any("receiver state accessor" in reason for reason in report["reasons"])


def test_unmodeled_source_effect_caps_target_quality():
    report = semantic_target_quality_report(
        "pdoc/extract.py:invalidate_caches",
        ranked_candidates=["pdoc/extract.py:invalidate_caches"],
        source_evidence=["pdoc/extract.py:invalidate_caches"],
        structural_evidence={
            "source_body_complete": True,
            "observed_side_effects": ["memory_state"],
        },
        input_contract={"module_name": "str"},
        output_contract={"result": "VoidSideEffect"},
        side_effect_contract={"declared": []},
    )

    assert report["score"] <= 74
    assert any("absent from the declared" in reason for reason in report["reasons"])
