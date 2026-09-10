from runtime.first_slice_viability import first_slice_viability


def test_logging_sink_is_viable_only_with_ready_fake_transport_boundary():
    context = {
        "dependency_readiness": {"status": "ready"},
        "snippet": {
            "target_binding": "method_symbol",
            "owner_class": "JournalStream",
            "text": (
                "def __call__(self, data):\n"
                "    journal.send(data['data'], STREAM=data['name'])\n"
            ),
            "structural_contract": {
                "source_body_complete": True,
                "state_mutation": False,
                "observed_side_effects": ["network"],
            },
        },
        "side_effects": ["network"],
    }

    result = first_slice_viability(
        "ExtendedJournalHandler/circus_journal.py:JournalStream.__call__",
        context,
    )

    assert result["status"] == "eligible"
    assert result["reselection_required"] is False
    assert any(
        row["rule_id"] == "logging_sink_adapter_boundary"
        for row in result["matched_rules"]
    )
