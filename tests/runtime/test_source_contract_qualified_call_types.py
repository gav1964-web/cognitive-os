from runtime.source_contract_semantics import infer_source_contract


def test_datetime_timestamp_call_proves_numeric_input_contract():
    candidate = {
        "signature": {"args": [{"name": "timestamp", "annotation": ""}]},
        "snippet": (
            "def format_timestamp(timestamp):\n"
            "    value = datetime.datetime.utcfromtimestamp(timestamp)\n"
            "    return value.strftime('%Y-%m-%d')\n"
        ),
    }

    evidence = infer_source_contract(candidate)

    assert evidence["argument_usage_types"] == {"timestamp": "NumberLike"}
