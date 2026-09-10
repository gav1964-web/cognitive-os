from __future__ import annotations

import sys

from tools.canonical_verify import verification_commands


def test_canonical_verification_covers_integrity_lint_and_both_test_scopes():
    commands = dict(verification_commands())

    assert set(commands) == {
        "registry_doctor",
        "config_doctor",
        "repo_lint",
        "project_boundaries",
        "compileall",
        "core_tests",
        "plugin_tests",
        "package_tests",
    }
    assert commands["core_tests"][:4] == [sys.executable, "-m", "pytest", "tests"]
    assert commands["plugin_tests"][:4] == [sys.executable, "-m", "pytest", "plugins"]


def test_canonical_verification_can_skip_expensive_test_scopes():
    assert set(dict(verification_commands(include_tests=False))) == {
        "registry_doctor",
        "config_doctor",
        "repo_lint",
        "project_boundaries",
        "compileall",
    }


def test_canonical_verification_scopes_basetemp_to_run_identity():
    commands = dict(verification_commands(run_id="run-123"))

    assert "--basetemp=.pytest-tmp/run-123/c" in commands["core_tests"]
    assert "--basetemp=.pytest-tmp/run-123/p" in commands["plugin_tests"]
