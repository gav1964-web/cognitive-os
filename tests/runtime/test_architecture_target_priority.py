from runtime.architecture_target_priority import (
    architecture_target_score,
    rank_architecture_targets,
    source_target_values,
)


POLICY = {
    "path_contains": [{"token": "/service.py", "weight": 20}],
    "symbol_prefixes": [{"token": "create_", "weight": 16}],
    "low_value_path_contains": [{"token": "/helpers.py", "weight": 12}],
    "low_value_symbol_prefixes": [{"token": "should_", "weight": 18}],
}


def test_architecture_boundary_ranks_before_convenience_helper():
    rows = ["pkg/helpers.py:should_retry", "pkg/service.py:resolve"]

    assert rank_architecture_targets(rows, POLICY) == [
        "pkg/service.py:resolve",
        "pkg/helpers.py:should_retry",
    ]


def test_source_order_is_stable_when_significance_is_equal():
    rows = ["pkg/a.py:normalize", "pkg/b.py:format"]

    assert rank_architecture_targets(rows, POLICY) == rows


def test_score_can_be_shared_with_reselection_ordering():
    assert architecture_target_score("pkg/service.py:resolve", POLICY) > architecture_target_score(
        "pkg/helpers.py:should_retry", POLICY
    )


def test_source_target_values_normalizes_analyzer_capability_rows():
    assert source_target_values([
        "pkg/api.py:create_item",
        {"path": "pkg/service.py", "name": "resolve"},
    ]) == ["pkg/api.py:create_item", "pkg/service.py:resolve"]


def test_semantic_contract_profile_affects_architect_initial_order():
    rows = [
        "src/pluggy/_hooks.py:varnames",
        "src/pluggy/_hooks.py:call_extra",
    ]

    assert rank_architecture_targets(rows, POLICY)[0] == "src/pluggy/_hooks.py:call_extra"


def test_package_identity_parser_outranks_import_coupled_publishing_helper():
    rows = [
        "attestations.py:compose_attestation_mapping",
        "print-pkg-names.py:safe_parse_pkg_name",
    ]

    assert rank_architecture_targets(rows, POLICY)[0] == "print-pkg-names.py:safe_parse_pkg_name"
