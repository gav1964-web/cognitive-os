from runtime.source_contract_semantics import infer_source_contract


def test_returned_constructor_call_is_inferred_as_constructed_object():
    local = infer_source_contract({"snippet": "def build():\n    return Client()"})
    qualified = infer_source_contract(
        {"snippet": "def build():\n    return transport.AsyncClient(timeout=5)"}
    )

    assert local["inferred_output_type"] == "ConstructedObject[Client]"
    assert qualified["inferred_output_type"] == "ConstructedObject[AsyncClient]"
