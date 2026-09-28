import json

from runtime.promoted_candidate_selection_policies import apply_preflight_selection_policies


def test_legacy_policy_without_reproduction_state_is_quarantined(tmp_path):
    path = tmp_path / "policies.json"
    path.write_text(json.dumps({
        "schema_version": "promoted_candidate_selection_policies.v1",
        "policies": [{
            "id": "legacy",
            "trigger": "executable_acceptance_rejected",
            "trigger_signals": ["meta_only"],
            "selection_mode": "stable_partition_existing_candidates",
            "preflight_trigger_requirements": {
                "output_inference_basis": ["no_value_return"],
            },
            "structural_requirements": {"min_return_paths": 1},
            "numeric_bonus": False,
        }],
    }), encoding="utf-8")
    ranked = [
        {"source": "write", "evidence": {"snippet": "def write():\n    pass"}},
        {"source": "build", "evidence": {"snippet": "def build():\n    return 1"}},
    ]

    result = apply_preflight_selection_policies(ranked, path=str(path))

    assert [row["source"] for row in result] == ["write", "build"]
