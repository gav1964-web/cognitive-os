from runtime.source_contract_semantics import infer_source_contract


def test_unpadding_call_is_inferred_as_bytes():
    evidence = infer_source_contract(
        {
            "signature": {"args": [{"name": "value", "annotation": ""}], "returns": ""},
            "snippet": "def decrypt(value):\n    return Crypto.__unpad(cipher.decrypt(value))",
        }
    )

    assert evidence["inferred_output_type"] == "bytes"
