from runtime.semantic_target_profiles import contract_for_target, semantic_score_adjustments


def test_gitlab_holdout_contract_families_are_profiled():
    cases = {
        "wm.py:move_to_workspace": "desktop_workspace_command_boundary",
        "jinja2_ansible_filters/ansible_utils.py:merge_hash": "recursive_mapping_merge_boundary",
        "collector.py:limit_extractor": "rate_limit_header_value_parser",
        "freeotp_migrate.py:read_tokens": "otp_token_migration_reader",
    }

    for target, family in cases.items():
        contract = contract_for_target(target)
        assert contract["contract_family"] == family
        assert contract["input_contract"]
        assert contract["output_contract"]
        assert contract["validation_gates"]
        assert contract["failure_modes"]
        assert semantic_score_adjustments(target)["score_delta"] >= 20
