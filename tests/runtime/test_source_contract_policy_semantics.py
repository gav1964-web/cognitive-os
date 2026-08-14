from runtime.source_contract_semantics import infer_source_contract


def test_file_extension_policy_proves_boolean_output_and_family_evidence():
    evidence = infer_source_contract({
        "signature": {"args": [{"name": "filename"}]},
        "snippet": (
            "def allowed_file(filename):\n"
            "    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS"
        ),
    })

    assert evidence["inferred_output_type"] == "bool"
    assert evidence["file_extension_policy"] is True


def test_string_concatenation_with_numeric_formatting_produces_string_output():
    evidence = infer_source_contract({
        "snippet": "def summarize(name, score):\n    result = name + ': ' + str(score)\n    return result",
    })

    assert evidence["inferred_output_type"] == "str"


def test_structural_contract_uses_configured_external_effect_markers():
    evidence = infer_source_contract({
        "snippet": (
            "async def authorized(pool, room):\n"
            "    found = await pool.sismember('rooms', room)\n"
            "    print(found)\n"
            "    return bool(found)"
        ),
    })

    assert evidence["observed_side_effects"] == ["network", "observability"]
