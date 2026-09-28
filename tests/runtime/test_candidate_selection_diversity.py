from runtime.improvement_plugins.candidate_selection_discriminator import _candidate_sources


def test_shadow_budget_spans_candidate_name_families_before_duplicates():
    candidates = [
        "admin.py:FirstAdmin.has_add_permission",
        "admin.py:FirstAdmin.has_change_permission",
        "admin.py:SecondAdmin.has_add_permission",
        "admin.py:SecondAdmin.has_change_permission",
        "admin.py:SecondAdmin.approve_entries",
        "services.py:build_activity_summary",
    ]
    packet = {"artifact_evidence": {"architecture_decision": {
        "source_candidate_pool": candidates,
    }}}

    selected = _candidate_sources(
        packet,
        diagnosis={},
        source="helpers.py:Record.has_main",
        config={"maximum_shadow_challengers": 4},
    )

    assert selected[0] == "admin.py:FirstAdmin.has_add_permission"
    assert "admin.py:SecondAdmin.approve_entries" in selected
    assert "services.py:build_activity_summary" in selected
    assert selected.index("admin.py:SecondAdmin.approve_entries") < selected.index(
        "admin.py:FirstAdmin.has_change_permission"
    )
