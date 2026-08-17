from runtime.source_contract_semantics import infer_source_contract


def test_unpadding_call_is_inferred_as_bytes():
    evidence = infer_source_contract(
        {
            "signature": {"args": [{"name": "value", "annotation": ""}], "returns": ""},
            "snippet": "def decrypt(value):\n    return Crypto.__unpad(cipher.decrypt(value))",
        }
    )

    assert evidence["inferred_output_type"] == "bytes"


def test_password_verification_proves_string_inputs_and_boolean_output():
    evidence = infer_source_contract(
        {
            "signature": {"args": [{"name": "plain", "annotation": ""}, {"name": "hashed", "annotation": ""}]},
            "snippet": "def verify_password(plain, hashed):\n    return pwd_context.verify(plain, hashed)",
        }
    )

    assert evidence["argument_usage_types"] == {"plain": "str", "hashed": "str"}
    assert evidence["inferred_output_type"] == "bool"
