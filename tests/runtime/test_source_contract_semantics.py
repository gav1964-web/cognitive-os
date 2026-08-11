from runtime.source_contract_semantics import infer_source_contract, structural_quality_adjustment
from runtime.target_quality import semantic_target_quality_report


def test_explicit_none_annotation_produces_void_contract():
    evidence = infer_source_contract(
        {
            "signature": {"args": [], "returns": "None"},
            "snippet": "def dump_bundles() -> None:\n    write_rows()",
        }
    )

    assert evidence["inferred_output_type"] == "VoidSideEffect"
    assert evidence["output_inference_basis"] == "explicit_none_annotation"


def test_returned_mapping_variable_is_inferred_from_assignment():
    evidence = infer_source_contract(
        {
            "signature": {"args": [{"name": "config", "annotation": ""}], "returns": ""},
            "snippet": "def convert(config):\n    kwargs = {}\n    kwargs.update(config)\n    return kwargs",
        }
    )

    assert evidence["inferred_output_type"] == "MappingLike"
    assert evidence["output_inference_basis"] == "return_expression"


def test_docstring_can_supply_mapping_semantics_when_return_expression_is_opaque():
    evidence = infer_source_contract(
        {
            "signature": {"args": [{"name": "config", "annotation": ""}], "returns": ""},
            "snippet": 'def convert(config):\n    """Convert options to kwargs accepted by setup."""\n    return process(config)',
        }
    )

    assert evidence["inferred_output_type"] == "MappingLike"
    assert evidence["output_inference_basis"] == "docstring_semantics"


def test_structural_quality_requires_source_bound_contract_evidence():
    report = semantic_target_quality_report(
        "core.py:convert",
        ranked_candidates=["core.py:convert"],
        source_evidence=["core.py:convert"],
        structural_evidence={
            "source_body_available": True,
            "source_body_complete": True,
            "docstring_available": True,
            "explicit_return_annotation": "dict[str, str]",
        },
        input_contract={"config": "MappingLike"},
        output_contract={"result": "dict[str, str]"},
    )

    assert report["score"] >= 95
    assert "source-bound input shapes are concrete" in report["reasons"]


def test_structural_quality_does_not_reward_generic_inferred_shapes():
    score, reasons = structural_quality_adjustment(
        {"source_body_available": False, "explicit_return_annotation": ""},
        input_contract={"payload": "InferredInput"},
        output_contract={"result": "InferredOutput"},
    )

    assert score == 0
    assert reasons == []


def test_truncated_callable_retains_docstring_but_marks_body_incomplete():
    evidence = infer_source_contract(
        {
            "signature": {"args": [{"name": "config", "annotation": ""}], "returns": ""},
            "snippet": 'def convert(config):\n    """Convert options to kwargs."""\n    values = {\n        "x": 1,',
        }
    )

    assert evidence["source_body_available"] is True
    assert evidence["source_body_complete"] is False
    assert evidence["docstring_available"] is True


def test_truncated_numpy_docstring_preserves_argument_and_return_shapes():
    evidence = infer_source_contract(
        {
            "signature": {"args": [{"name": "p", "annotation": ""}], "returns": ""},
            "snippet": 'def draw(p):\n    """Draw.\n\n    Parameters\n    ----------\n    p : QPainter\n\n    Returns\n    -------\n    tuple\n        Specs',
        }
    )

    assert evidence["docstring_argument_types"] == {"p": "QPainter"}
    assert evidence["inferred_output_type"] == "TupleLike"
    assert evidence["output_inference_basis"] == "docstring_return_contract"


def test_truncated_callable_without_visible_return_does_not_claim_void_output():
    evidence = infer_source_contract(
        {
            "signature": {"args": [{"name": "request", "annotation": ""}], "returns": ""},
            "snippet": "def chooser(request):\n    rows = load_rows(\n        request.user,",
        }
    )

    assert evidence["source_body_complete"] is False
    assert evidence["inferred_output_type"] == "InferredOutput"


def test_local_mapping_updates_are_not_external_state_mutation():
    local = infer_source_contract(
        {"snippet": "def build():\n    result = {}\n    result['x'] = 1\n    return result"}
    )
    external = infer_source_contract(
        {"snippet": "def update(obj):\n    obj.value = 1"}
    )

    assert local["state_mutation"] is False
    assert external["state_mutation"] is True
