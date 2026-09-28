"""A venv executable path carries environment identity even when it is a symlink."""
import sys
from pathlib import Path

import pytest

from runtime import project_native_failure_environment as environment


@pytest.mark.parametrize('configured', [False, True])
def test_interpreter_resolution_preserves_venv_symlink(tmp_path, monkeypatch, configured):
    executable = tmp_path / 'venv' / 'bin' / 'python'
    executable.parent.mkdir(parents=True)
    try:
        executable.symlink_to(sys.executable)
    except OSError:
        pytest.skip('symlink creation unavailable')
    monkeypatch.setattr(environment.sys, 'executable', str(executable))
    intake = {}
    if configured:
        intake['project_interpreter_profiles'] = {
            'demo': {'major': sys.version_info.major, 'minor': sys.version_info.minor},
        }
        monkeypatch.setattr(environment, '_probe_python_version', lambda path: sys.version_info[:3])
    result = environment._resolve_project_interpreter('demo', intake)
    assert result['executable'] == str(executable.absolute())
    assert Path(result['executable']) != executable.resolve()
