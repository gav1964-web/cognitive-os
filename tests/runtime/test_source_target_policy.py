from __future__ import annotations

from runtime.source_target_policy import (
    implementation_target_violation,
    load_role_source_policy,
    scope_policy_int,
    scope_policy_list,
)


def test_role_source_policy_exposes_scope_selection_kb():
    policy = load_role_source_policy()

    assert "scope_selection_policy" in policy
    assert {"src", "lib"} <= set(scope_policy_list("preferred_roots", policy))
    assert "tests" in set(scope_policy_list("disfavored_roots", policy))
    assert "pyproject.toml" in set(scope_policy_list("manifest_names", policy))
    assert scope_policy_int("aliased_core_max_gap", 0, policy) == 8


def test_role_source_policy_keeps_runtime_package_named_testing_allowed():
    assert implementation_target_violation("src/zope/testing/formparser.py:parse")["status"] == "allowed"
    assert implementation_target_violation("tests/test_formparser.py:parse")["status"] == "blocked_no_safe_candidate"


def test_role_source_policy_blocks_root_task_runner_module():
    assert implementation_target_violation("tasks.py:release")["status"] == "blocked_no_safe_candidate"


def test_role_source_policy_blocks_profiling_and_server_config_targets():
    blocked = [
        "conftest.py:pytest_configure",
        "profiling/pyspy.py:vector_search",
        "bin/gunicorn_conf.py:post_fork",
    ]

    for target in blocked:
        assert implementation_target_violation(target)["status"] == "blocked_no_safe_candidate"
