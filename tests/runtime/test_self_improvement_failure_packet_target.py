from runtime.self_improvement_training import _failure_packet


def test_failure_packet_preserves_rejected_quality_target():
    packet = _failure_packet(
        {
            "project_min_score": 6.47,
            "role_scores": {"spec_writer": 6.47},
            "status": "blocked_ok",
            "selected_extraction_candidate": None,
            "selected_candidate_quality": {
                "target": "pkg/helpers.py:has_main",
                "status": "poor",
            },
            "warnings": [],
            "downstream_evidence": {},
            "artifacts": {},
        },
        9.7,
    )

    assert packet["selected_candidate"] == "pkg/helpers.py:has_main"
