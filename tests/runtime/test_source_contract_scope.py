from runtime.source_contract_semantics import infer_source_contract


def test_nested_returns_do_not_define_outer_callable_contract():
    candidate = {
        "signature": {
            "args": [{"name": "row", "annotation": ""}, {"name": "filename", "annotation": ""}],
            "returns": "",
        },
        "snippet": """def render(row, filename):
    def calculate(value):
        return {"result": value}
    if row.data.get("payload") is None:
        return
    plotting.savefig(filename)
""",
    }

    evidence = infer_source_contract(candidate)

    assert evidence["inferred_output_type"] == "VoidSideEffect"
    assert evidence["output_inference_basis"] == "no_value_return"
    assert evidence["return_paths"] == 1
    assert evidence["argument_usage_types"]["row"] == "ProtocolLike"
    assert "filesystem" in evidence["observed_side_effects"]
