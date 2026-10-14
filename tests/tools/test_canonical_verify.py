from __future__ import annotations

import sys

from tools.canonical_verify import _run, verification_commands


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
    assert "--import-mode=importlib" in commands["plugin_tests"]
    assert commands["repo_lint"] == [sys.executable, "tools/finalize_stage.py", "--root", "."]


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
    for name in ('core_tests', 'plugin_tests', 'package_tests'):
        assert f'--junitxml=artifacts/verification/run-123/{name}.xml' in commands[name]


def test_failure_preserves_full_streams_beyond_report_tail(tmp_path):
    result = _run(root=tmp_path, name='core_tests', run_id='failed-run', command=[
        sys.executable, '-c',
        "import sys;print('FIRST FAILURE');print('x'*3000);"
        "print('diagnostic',file=sys.stderr);sys.exit(3)",
    ])
    assert result['status'] == 'failed' and result['returncode'] == 3
    assert 'FIRST FAILURE' not in result['stdout_tail']
    assert (tmp_path / result['stdout_path']).read_text().startswith('FIRST FAILURE')
    assert (tmp_path / result['stderr_path']).read_text().strip() == 'diagnostic'
    assert result['junit_path'] is None
