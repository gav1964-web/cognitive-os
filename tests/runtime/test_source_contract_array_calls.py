from runtime.source_contract_semantics import infer_source_contract


def test_numpy_array_assignment_proves_array_output():
    evidence = infer_source_contract(
        {
            "signature": {"args": [{"name": "data", "annotation": "object"}]},
            "snippet": "def project(data):\n    result = np.array(data)\n    return result",
        }
    )

    assert evidence["inferred_output_type"] == "ArrayLike"


def test_array_slice_assignment_preserves_array_output():
    evidence = infer_source_contract(
        {
            "signature": {"args": [{"name": "data", "annotation": ""}]},
            "snippet": "def truncate(data):\n    result = data[1:-1, :]\n    return result",
        }
    )

    assert evidence["argument_usage_types"]["data"] == "ArrayLike"
    assert evidence["inferred_output_type"] == "ArrayLike"
