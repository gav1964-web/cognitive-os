from runtime.first_slice_viability import first_slice_viability


def _assert_eligible(context):
    result = first_slice_viability("output.py:add_components", context)
    assert result["reselection_required"] is False


def test_annotated_protocol_from_source_text_is_declared():
    _assert_eligible({
        "snippet": {
            "target_binding": "function_symbol",
            "text": "def add_components(branch: Tree):\n    branch.add('item')",
            "structural_contract": {"argument_usage_types": {"branch": "ProtocolLike"}},
        }
    })


def test_context_signature_survives_string_snippet_normalization():
    _assert_eligible({
        "snippet": "def add_components(branch):\n    branch.add('item')",
        "signature": {"args": [{"name": "branch", "annotation": "Tree"}]},
        "structural_contract": {"argument_usage_types": {"branch": "ProtocolLike"}},
    })


def test_context_contract_survives_mapping_snippet_normalization():
    _assert_eligible({
        "snippet": {"text": "def add_components(branch):\n    branch.add('item')"},
        "signature": {"args": [{"name": "branch", "annotation": "Tree"}]},
        "structural_contract": {"argument_usage_types": {"branch": "ProtocolLike"}},
    })


def test_annotated_protocol_is_declared_without_structural_summary():
    _assert_eligible({
        "snippet": {"text": "def add_components(branch: Tree):\n    branch.add('item')"}
    })
