from runtime.source_contract_semantics import infer_source_contract


def test_sequence_translate_return_is_a_concrete_string():
    contract = infer_source_contract(
        {
            "signature": {"args": [{"name": "sequence", "annotation": "str"}], "returns": ""},
            "snippet": "def reverse_complement(sequence):\n    return sequence[::-1].translate(TABLE)\n",
        }
    )

    assert contract["inferred_output_type"] == "str"
    assert contract["output_inference_basis"] == "return_expression"
