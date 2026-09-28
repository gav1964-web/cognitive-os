from runtime.source_contract_semantics import infer_source_contract


def test_isinstance_uses_declared_runtime_type_instead_of_array_guess():
    evidence = infer_source_contract(
        {
            "signature": {"args": [{"name": "arity"}, {"name": "wrap"}]},
            "snippet": (
                "def validate(arity, wrap):\n"
                "    if not isinstance(arity, int):\n"
                "        raise ValueError\n"
                "    if not isinstance(wrap, bool):\n"
                "        raise ValueError"
            ),
        }
    )

    assert evidence["argument_usage_types"] == {"arity": "int", "wrap": "bool"}
