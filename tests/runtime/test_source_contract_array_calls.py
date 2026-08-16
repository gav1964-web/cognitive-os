from runtime.source_contract_semantics import infer_source_contract


def test_numpy_array_assignment_proves_array_output():
    evidence = infer_source_contract(
        {
            "signature": {"args": [{"name": "data", "annotation": "object"}]},
            "snippet": "def project(data):\n    result = np.array(data)\n    return result",
        }
    )

    assert evidence["inferred_output_type"] == "ArrayLike"
