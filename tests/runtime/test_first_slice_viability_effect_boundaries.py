from runtime.first_slice_viability import first_slice_viability


def _context(*effects: str, state_mutation: bool = False):
    return {
        "snippet": {
            "structural_contract": {
                "observed_side_effects": list(effects),
                "state_mutation": state_mutation,
            }
        }
    }


def test_direct_memory_mutation_requires_pure_alternative():
    result = first_slice_viability(
        "summary.py:build_summary", _context(state_mutation=True)
    )

    assert result["reselection_required"] is True
    assert any(row["rule_id"] == "direct_memory_state_boundary" for row in result["matched_rules"])


def test_filesystem_hash_requires_fixture_or_pure_alternative():
    result = first_slice_viability(
        "builder.py:calculate_hash", _context("filesystem_read")
    )

    assert result["reselection_required"] is True
    assert any(row["rule_id"] == "filesystem_hash_boundary" for row in result["matched_rules"])
    assert first_slice_viability(
        "loader.py:load_trace", _context("filesystem_read")
    )["reselection_required"] is False


def test_filesystem_rebuild_requires_pure_inner_contract():
    result = first_slice_viability(
        "stats.py:rebuild_daily_stats", _context("filesystem_write")
    )

    assert result["reselection_required"] is True
    assert any(row["rule_id"] == "filesystem_rebuild_boundary" for row in result["matched_rules"])


def test_observable_application_bootstrap_requires_reselection():
    result = first_slice_viability("application.py:main", _context("observability"))

    assert result["reselection_required"] is True
    assert any(row["rule_id"] == "observability_bootstrap_boundary" for row in result["matched_rules"])
    assert first_slice_viability(
        "reporting.py:debug_response", _context("observability")
    )["reselection_required"] is False
