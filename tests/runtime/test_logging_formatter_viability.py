from runtime.first_slice_viability import first_slice_viability


def test_logging_formatter_record_boundary_overrides_generic_method_blocks():
    result = first_slice_viability(
        "source/simple_logging/severity_padding_formatter.py:format",
        {
            "dependency_readiness": {"status": "ready"},
            "side_effects": ["memory_state"],
            "snippet": {
                "target_binding": "method_symbol",
                "owner_class": "SeverityPaddingFormatter",
                "text": (
                    "def format(self, record):\n"
                    "    record.levelname = record.levelname.upper()\n"
                    "    return super().format(record)"
                ),
                "structural_contract": {
                    "argument_count": 1,
                    "typed_argument_count": 0,
                    "argument_usage_types": {"record": "ProtocolLike"},
                    "observed_side_effects": ["memory_state"],
                    "source_body_complete": True,
                    "state_mutation": True,
                },
            },
        },
    )

    assert result["status"] == "eligible"
    assert result["reselection_required"] is False
    assert "logging_formatter_record_boundary" in {
        row["rule_id"] for row in result["matched_rules"]
    }
