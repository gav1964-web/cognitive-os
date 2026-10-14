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


def test_mapping_subscript_selector_is_inferred_as_key_like():
    evidence = infer_source_contract({
        "signature": {"args": [{"name": "origin"}, {"name": "by_key"}]},
        "snippet": "def order(origin, by_key):\n    return sorted(origin, key=lambda item: item[by_key])",
    })

    assert evidence["argument_usage_types"]["by_key"] == "KeyLike"


def test_or_coalesce_returns_operand_shape_instead_of_boolean():
    evidence = infer_source_contract({
        "signature": {"args": [{"name": "cls"}, {"name": "token"}]},
        "snippet": (
            "@classmethod\n"
            "def require_token(cls, token=None):\n"
            "    token = token or cls.default_token\n"
            "    if not token:\n"
            "        raise ValueError('token required')\n"
            "    return token\n"
        ),
    })

    assert evidence["inferred_output_type"] == "AttributeValue"


def test_string_line_concatenation_infers_executable_string_contract():
    evidence = infer_source_contract({
        "signature": {"args": [
            {"name": "prefix"}, {"name": "string"}, {"name": "plain_prefix"},
        ]},
        "snippet": (
            "def indented_lines(prefix, string, plain_prefix=None):\n"
            "    lines = str(string).splitlines() or ['']\n"
            "    return [prefix + lines[0]] + [\n"
            "        ' ' * len(plain_prefix or prefix) + line for line in lines[1:]\n"
            "    ]\n"
        ),
    })

    assert evidence["argument_usage_types"]["prefix"] == "str"
    assert evidence["inferred_output_type"] == "SequenceLike"
