from __future__ import annotations

from tools.github_implementer_probe import _is_forbidden_source, _verification_commands_project_scoped


def test_github_implementer_probe_rejects_integration_test_targets():
    assert _is_forbidden_source("integration_tests/python_modules/pkg/kind.py:create_cluster")
    assert _is_forbidden_source("docs/examples/pkg.py:demo")


def test_github_implementer_probe_requires_project_scoped_verification_commands():
    assert _verification_commands_project_scoped(["python -m pytest -q", "python -m compileall ."])
    assert not _verification_commands_project_scoped(
        ["python -m compileall runtime tools plugins", "python tools/mvp_acceptance.py --root . --skip-pytest"]
    )
