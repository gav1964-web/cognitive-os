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


def test_awaited_repository_get_result_is_inferred_as_entity():
    evidence = infer_source_contract(
        {
            "signature": {"args": [{"name": "id", "annotation": "int"}], "returns": ""},
            "snippet": "async def delete_note(id: int):\n    note = await crud.get(id)\n    return note",
        }
    )

    assert evidence["inferred_output_type"] == "EntityLike"
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


def test_argument_constraints_infer_optional_literal_type():
    evidence = infer_source_contract(
        {
            "signature": {"args": [{"name": "media_type", "annotation": ""}]},
            "snippet": (
                "def chooser(media_type=None):\n"
                "    if media_type == 'audio':\n        return 1\n"
                "    if media_type == 'video':\n        return 2\n"
                "    if media_type is None:\n        return 3\n"
            ),
        }
    )

    assert evidence["argument_constraint_types"] == {
        "media_type": "Optional[Literal['audio', 'video']]"
    }


def test_structural_quality_rewards_explicit_failure_contract():
    evidence = infer_source_contract(
        {
            "signature": {"args": [{"name": "value", "annotation": "str"}], "returns": "str"},
            "snippet": "def validate(value: str) -> str:\n    if not value:\n        raise ValueError('empty')\n    return value",
        }
    )

    score, reasons = structural_quality_adjustment(
        evidence,
        input_contract={"value": "str"},
        output_contract={"result": "str"},
        side_effect_contract={"declared": []},
    )

    assert score >= 25
    assert "explicit failure paths prove a negative contract" in reasons


def test_generator_body_produces_iterator_contract():
    evidence = infer_source_contract(
        {
            "signature": {"args": [{"name": "rows", "annotation": "list[str]"}]},
            "snippet": "def generate_rows(rows):\n    for row in rows:\n        yield row.strip()",
        }
    )

    assert evidence["inferred_output_type"] == "IteratorLike"
    assert evidence["output_inference_basis"] == "yield_expression"


def test_argument_usage_and_receiver_return_produce_concrete_contracts():
    evidence = infer_source_contract(
        {
            "signature": {"args": [{"name": "rows", "annotation": ""}]},
            "snippet": "def add_rows(self, rows):\n    for row in rows:\n        self.add(row)\n    return self",
        }
    )

    assert evidence["argument_usage_types"] == {"rows": "IterableLike"}
    assert evidence["inferred_output_type"] == "ReceiverState"


def test_deleted_argument_key_proves_mapping_mutation_and_return_shape():
    evidence = infer_source_contract(
        {
            "signature": {
                "args": [
                    {"name": "logger", "annotation": ""},
                    {"name": "level", "annotation": ""},
                    {"name": "event", "annotation": ""},
                ]
            },
            "snippet": (
                "def filter_taskname(logger, level, event):\n"
                "    if 'taskName' in event:\n"
                "        del event['taskName']\n"
                "    return event"
            ),
        }
    )

    assert evidence["argument_usage_types"]["event"] == "MappingLike"
    assert evidence["inferred_output_type"] == "MappingLike"
    assert evidence["state_mutation"] is True


def test_tensor_to_image_method_chain_proves_array_output():
    evidence = infer_source_contract(
        {
            "signature": {"args": [{"name": "tensor", "annotation": ""}]},
            "snippet": (
                "def tensor2image(tensor):\n"
                "    image = tensor[0].cpu().float().numpy()\n"
                "    return image.astype('uint8')"
            ),
        }
    )

    assert evidence["argument_usage_types"] == {"tensor": "IndexableLike"}
    assert evidence["inferred_output_type"] == "ArrayLike"


def test_string_replacement_preserves_argument_and_output_type():
    evidence = infer_source_contract(
        {"signature": {"args": [{"name": "message", "annotation": ""}]}, "snippet": "def alter(message):\n    message = message.replace('old', 'new')\n    return message"}
    )
    assert evidence["argument_usage_types"] == {"message": "str"}
    assert evidence["inferred_output_type"] == "str"


def test_subscript_assignment_proves_local_mapping_result():
    evidence = infer_source_contract(
        {"snippet": "def tokenize(text):\n    result = tokenizer(text)\n    result['labels'] = []\n    return result"}
    )
    assert evidence["inferred_output_type"] == "MappingLike"


def test_loop_and_boolean_usage_prove_scalar_argument_types():
    evidence = infer_source_contract(
        {
            "signature": {"args": [{"name": "count"}, {"name": "enabled"}]},
            "snippet": "def run(count, enabled):\n    for _ in range(count):\n        if enabled and count:\n            pass",
        }
    )
    assert evidence["argument_usage_types"] == {"count": "int", "enabled": "bool"}


def test_dbapi_execute_proves_sql_input_and_result_shape():
    evidence = infer_source_contract(
        {"signature": {"args": [{"name": "sql"}]}, "snippet": "def execute(sql):\n    result = cursor.execute(sql)\n    return result"}
    )
    assert evidence["argument_usage_types"] == {"sql": "SQLLike"}
    assert evidence["inferred_output_type"] == "DatabaseResult"


def test_request_call_result_proves_response_shape_through_local_variable():
    evidence = infer_source_contract(
        {"snippet": "def update(payload):\n    response = client.perform_request(payload)\n    return response"}
    )
    assert evidence["inferred_output_type"] == "ResponseLike"


def test_attribute_access_proves_protocol_argument_shape():
    evidence = infer_source_contract(
        {"signature": {"args": [{"name": "options", "annotation": "object"}]}, "snippet": "def run(options):\n    return options.mode"}
    )
    assert evidence["argument_usage_types"] == {"options": "ProtocolLike"}


def test_tensor_reduction_arithmetic_proves_array_output():
    evidence = infer_source_contract(
        {"snippet": "def pool(values, mask):\n    total = torch.sum(values * mask, 1)\n    return total / torch.clamp(mask.sum(1), min=1e-9)"}
    )
    assert evidence["inferred_output_type"] == "ArrayLike"


def test_multiple_structured_return_shapes_produce_union_contract():
    evidence = infer_source_contract(
        {"snippet": "def overlay(value):\n    if value:\n        return make_item(value)\n    return [value]"}
    )
    assert evidence["inferred_output_type"] == "Union[ItemLike, SequenceLike]"


def test_numpy_style_named_return_uses_type_after_colon():
    evidence = infer_source_contract(
        {"snippet": "def predict(values):\n    \"\"\"Returns\n    -------\n    p : array of shape [n, k]\n    \"\"\"\n    return np.log(values)"}
    )
    assert evidence["inferred_output_type"] == "ArrayLike"


def test_format_call_proves_string_output():
    evidence = infer_source_contract(
        {"snippet": "def hello(version):\n    message = 'Python {}'.format(version)\n    return message"}
    )
    assert evidence["inferred_output_type"] == "str"


def test_source_contract_preserves_extracted_decorators():
    evidence = infer_source_contract({"snippet": "def hello():\n    return 'ok'", "decorators": ["app.route"]})
    assert evidence["decorators"] == ["app.route"]

    precomputed = infer_source_contract(
        {"structural_contract": {"inferred_output_type": "str"}, "decorators": ["app.route"]}
    )
    assert precomputed["decorators"] == ["app.route"]


def test_value_return_overrides_incorrect_none_annotation():
    evidence = infer_source_contract(
        {"signature": {"returns": "None"}, "snippet": "def task() -> None:\n    return entity.id"}
    )

    assert evidence["inferred_output_type"] == "AttributeValue"
    assert evidence["output_inference_basis"] == "return_expression"
