from runtime.first_slice_viability import first_slice_viability


def test_logging_record_projection_accepts_source_derived_receiver_fixture():
    context = {
        "dependency_readiness": {"status": "ready"},
        "snippet": {
            "target_binding": "method_symbol",
            "owner_class": "SplunkHandler",
            "text": (
                "def format_record(self, record):\n"
                "    return {'event': self.format(record), 'host': self.hostname}\n"
            ),
            "structural_contract": {
                "source_body_complete": True,
                "state_mutation": False,
                "observed_side_effects": [],
            },
        },
    }

    result = first_slice_viability(
        "splunk_handler/__init__.py:SplunkHandler.format_record", context
    )

    assert result["status"] == "eligible"
    assert result["reselection_required"] is False
    assert any(
        row["rule_id"] == "logging_record_projection_boundary"
        for row in result["matched_rules"]
    )


def test_logging_record_projection_is_not_blocked_by_unrelated_file_dependencies():
    context = {
        "snippet": {
            "target_binding": "method_symbol",
            "owner_class": "MultiProcessingHandler",
            "text": (
                "def _format_record(self, record):\n"
                "    record.msg = record.msg % record.args\n"
                "    record.args = None\n"
                "    return record\n"
            ),
            "structural_contract": {
                "source_body_complete": True,
                "state_mutation": True,
                "observed_side_effects": ["memory_state"],
            },
        },
    }

    result = first_slice_viability(
        "multiprocessing_logging.py:MultiProcessingHandler._format_record", context
    )

    assert result["status"] == "eligible"
    assert result["reselection_required"] is False
