from runtime.source_contract_semantics import infer_source_contract


def test_connection_execute_and_comparison_prove_database_scalar_contract():
    evidence = infer_source_contract({
        "signature": {"args": [{"name": "con"}, {"name": "orgcode"}, {"name": "params"}]},
        "snippet": (
            "def load(con, orgcode, params):\n"
            "    row = con.execute(query.where(code == orgcode)).fetchone()\n"
            "    return {'id': params['id'], 'value': row['value']}"
        ),
    })

    assert evidence["observed_side_effects"] == ["database"]
    assert evidence["argument_usage_types"] == {
        "con": "ProtocolLike", "orgcode": "ScalarLike", "params": "IndexableLike"
    }
