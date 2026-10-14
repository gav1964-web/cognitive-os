import hashlib
import json
import subprocess
import sys


def invoke(root, *args):
    return subprocess.run([sys.executable, '-m', 'cognitive_inspect', *args], cwd=root,
                          capture_output=True, text=True, encoding='utf-8', timeout=20)


def test_cli_emits_bounded_json_without_running_or_mutating_sources(tmp_path):
    (tmp_path / 'a.py').write_text('raise RuntimeError("DO_NOT_EXECUTE")\n')
    (tmp_path / 'b.txt').write_text('data')
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in tmp_path.iterdir()}
    result = invoke(tmp_path, '.', '--max-files', '1')
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert len(data['files']) == 1
    assert data['skipped']['truncated_files'] == 1
    assert {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in tmp_path.iterdir()} == before


def test_cli_missing_path_and_invalid_budget_are_clear_errors(tmp_path):
    for args in [('missing',), ('.', '--max-files', '0')]:
        result = invoke(tmp_path, *args)
        assert result.returncode == 2
        assert not result.stdout and 'cognitive-inspect:' in result.stderr
        assert 'Traceback' not in result.stderr


def test_cli_help_is_available_without_project_access(tmp_path):
    result = invoke(tmp_path, '--help')
    assert result.returncode == 0 and '--max-depth' in result.stdout
