from runtime.first_slice_viability import first_slice_viability


def test_static_time_format_boundary_overrides_runtime_global_dependency():
    result = first_slice_viability(
        "handlers.py:_get_daily_index_name",
        {
            "dependency_readiness": {"status": "ready"},
            "snippet": {
                "target_binding": "method_symbol",
                "owner_class": "LogHandler",
                "decorators": ["staticmethod"],
                "text": (
                    "@staticmethod\n"
                    "def _get_daily_index_name(prefix):\n"
                    "    return '{}-{}'.format(prefix, datetime.now().strftime('%Y.%m.%d'))\n"
                ),
                "structural_contract": {
                    "source_body_complete": True,
                    "observed_side_effects": [],
                },
            },
            "unresolved_calls": ["datetime.now", "strftime"],
        },
    )

    assert result["status"] == "eligible"
    assert result["reselection_required"] is False
    assert any(
        row["rule_id"] == "static_time_format_boundary"
        for row in result["matched_rules"]
    )
