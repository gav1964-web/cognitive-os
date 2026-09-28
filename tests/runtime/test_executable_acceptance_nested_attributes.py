from runtime.executable_acceptance_contract_inference import infer_argument_samples


def test_infers_nested_object_from_parameter_attribute_reads(tmp_path):
    source = tmp_path / "response.py"
    source.write_text(
        "def render(response):\n"
        "    return response.request.method, response.request.url, response.status_code\n",
        encoding="utf-8",
    )

    assert infer_argument_samples(source, "render") == {
        "response": {
            "value": {
                "__fixture__": "declared_model",
                "type": "AcceptanceInput",
                "fields": {
                    "request": {
                        "__fixture__": "declared_model",
                        "type": "AcceptanceInput",
                        "fields": {"method": "sample", "url": "sample"},
                    },
                    "status_code": "sample",
                },
            },
            "source": "ast_parameter_attributes",
        }
    }


def test_parameter_method_is_not_replaced_by_plain_attribute(tmp_path):
    source = tmp_path / "response.py"
    source.write_text(
        "def decode(response):\n    return response.json(), response.meta.key\n",
        encoding="utf-8",
    )

    sample = infer_argument_samples(source, "decode")["response"]["value"]

    assert "json" not in sample["fields"]
    assert sample["fields"]["meta"]["fields"]["key"] == "sample"


def test_propagates_nested_fixture_through_local_formatter(tmp_path):
    source = tmp_path / "response.py"
    source.write_text(
        "def render(response):\n"
        "    return response.request.method, response.status_code\n\n"
        "def debug(response):\n"
        "    log(render(response))\n",
        encoding="utf-8",
    )

    inferred = infer_argument_samples(source, "debug")["response"]

    assert inferred["source"] == "local_call:render:ast_parameter_attributes"
    assert inferred["value"]["fields"]["request"]["fields"]["method"] == "sample"
