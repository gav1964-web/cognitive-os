"""Executable CLI contract: each plugin owns explicit, bounded test paths."""
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.check_plugins import main


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    calls = []
    result_code = [0]
    def load(root):
        return {p.parent.name: object() for p in (root/'plugins').glob('*/plugin.json')}
    monkeypatch.setitem(sys.modules, 'runtime.plugin_loader', SimpleNamespace(load_capabilities=load))
    monkeypatch.setattr(sys, 'argv', ['check_plugins', '--root', str(tmp_path)])
    def run(argv, **kwargs):
        calls.append(argv)
        paths = argv[5:]
        # Model pytest's stable exit codes instead of an assertion containing
        # a generator repr with a process-specific address in native evidence.
        code = result_code[0] if paths and all(Path(p).exists() for p in paths) else 4
        return subprocess.CompletedProcess(argv, code, 'native output', 'native error')
    monkeypatch.setattr('tools.check_plugins.subprocess.run', run)
    return tmp_path, calls, result_code


def plugin(root, name='alpha', **metadata):
    path = root/'plugins'/name/'plugin.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'id':name, **metadata}), encoding='utf-8')


def test_file(root, name):
    path = root/name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('def test_owned():\n    assert True\n', encoding='utf-8')
    return str(path.resolve())


test_file.__test__ = False


def test_migrated_file_is_selected(workspace):
    root, calls, _ = workspace
    plugin(root, test_paths=['tests/test_alpha.py'])
    expected = test_file(root, 'tests/test_alpha.py')
    assert main() == 0
    assert calls[0][5:] == [expected]


def test_legacy_directory_remains_supported(workspace):
    root, calls, _ = workspace
    plugin(root)
    test_file(root, 'plugins/alpha/tests/test_alpha.py')
    assert main() == 0
    assert calls[0][5:] == [str((root/'plugins/alpha/tests').resolve())]


def test_declared_paths_override_legacy_and_deduplicate(workspace):
    root, calls, _ = workspace
    paths = ['tests/test_shared.py','tests/test_shared.py']
    plugin(root,'zeta',test_paths=paths)
    plugin(root,'alpha',test_paths=paths)
    expected = test_file(root,'tests/test_shared.py')
    test_file(root,'plugins/alpha/tests/test_old.py')
    assert main() == 0
    assert calls[0][5:] == [expected]


@pytest.mark.parametrize('declaration', [[], '', None, [''], [17], ['missing.py'],
    ['../outside.py'], ['/outside.py'], ['C:\\outside.py'], ['tests/*.py'], ['tests/test_alpha.py::test_owned']])
def test_invalid_or_missing_ownership_fails_before_pytest(workspace, declaration):
    root, calls, _ = workspace
    plugin(root, test_paths=declaration)
    test_file(root,'plugins/alpha/tests/test_old.py')
    assert main() != 0
    assert calls == []


def test_missing_legacy_tests_fail_before_pytest(workspace):
    root, calls, _ = workspace
    plugin(root)
    assert main() != 0
    assert calls == []


def test_empty_directory_is_not_coverage(workspace):
    root, calls, _ = workspace
    plugin(root, test_paths=['tests/empty'])
    (root/'tests/empty').mkdir(parents=True)
    assert main() != 0
    assert calls == []


def test_mixed_valid_and_missing_plugin_fails_closed(workspace):
    root, calls, _ = workspace
    plugin(root,'alpha',test_paths=['tests/test_alpha.py'])
    test_file(root,'tests/test_alpha.py')
    plugin(root,'broken')
    assert main() != 0
    assert calls == []


def test_pytest_failure_is_preserved(workspace, capsys):
    root, calls, result_code = workspace
    plugin(root)
    test_file(root,'plugins/alpha/tests/test_alpha.py')
    result_code[0] = 1
    assert main() == 1
    output = capsys.readouterr()
    assert 'native output' in output.out and 'native error' in output.err


def test_no_plugins_never_runs_global_pytest(workspace):
    _, calls, _ = workspace
    assert main() != 0
    assert calls == []


def test_external_symlink_is_rejected(workspace, tmp_path_factory):
    root, calls, _ = workspace
    outside = tmp_path_factory.mktemp('outside')/'test_external.py'
    outside.write_text('def test_external(): pass\n',encoding='utf-8')
    linked = root/'tests/test_link.py'
    linked.parent.mkdir(parents=True)
    try:
        linked.symlink_to(outside)
    except OSError:
        pytest.skip('symlink creation unavailable for this account')
    plugin(root,test_paths=['tests/test_link.py'])
    assert main() != 0
    assert calls == []


def test_resolved_escape_is_rejected_without_symlink_privileges(workspace, monkeypatch):
    root, calls, _ = workspace
    plugin(root,test_paths=['tests/test_link.py'])
    linked = root/'tests/test_link.py'
    original = Path.resolve
    def resolve(path, *args, **kwargs):
        return root.parent/'outside.py' if path == linked else original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'resolve', resolve)
    assert main() != 0
    assert calls == []
