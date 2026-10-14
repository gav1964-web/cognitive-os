"""Copies preserve failure identity without erasing file-specific evidence."""
import json
import sys
from pathlib import Path

from runtime.native_failure_acceptance import _probe
from runtime.native_failure_acceptance import _replay_signature
from runtime.project_native_failure_binding import _stable_summary


def test_real_missing_file_repeats_across_distinct_project_copies(tmp_path):
    signatures = []
    for index, filename in enumerate(('first.dat', 'first.dat', 'second.dat')):
        project = tmp_path / f'project-{index}'
        project.mkdir()
        (project/'app.py').write_text('from pathlib import Path\ndef read():\n    return (Path(__file__).parent / '+repr(filename)+').read_text()\n')
        (project/'test_app.py').write_text('from app import read\ndef test_read():\n    assert read() == "value"\n')
        result = _probe(project, tmp_path/f'probe-{index}', ['test_app.py::test_read'], [], 30, Path(sys.executable))
        assert result['returncode'] == 1
        signatures.append(result['intake_signature'])
    assert signatures[0] == signatures[1]
    assert signatures[0] != signatures[2]


def test_only_bound_prefix_is_normalized(tmp_path):
    root = tmp_path/'source'
    source = str(root/'file.dat')
    encoded = json.dumps(source)[1:-1]
    normalized = _stable_summary('FileNotFoundError: '+encoded, project=root)
    assert normalized.endswith('<project>/file.dat')
    other = str(tmp_path/'source-other'/'file.dat')
    assert _stable_summary(other, project=root) == other
    assert _stable_summary('ValueError: 0xabc differs from 0xdef', project=root) == 'ValueError: 0xabc differs from 0xdef'


def test_native_selection_survives_project_test_changing_sys_argv(tmp_path):
    project = tmp_path/'project'
    project.mkdir()
    (project/'test_cli.py').write_text('import sys\ndef test_cli():\n    sys.argv[:]=["app"]\n    assert True\n')
    result = _probe(project, tmp_path/'probe', ['test_cli.py'], [], 30, Path(sys.executable), collect_nodeids=True)
    assert result['returncode'] == 0
    assert result['selected_nodeids'] == ['test_cli.py::test_cli']
    assert any(r['when']=='call' and r['outcome']=='passed' for r in result['test_reports'])


def test_rewritten_assertion_function_addresses_are_stable(tmp_path):
    project = tmp_path/'project'
    project.mkdir()
    (project/'app.py').write_text('def read():\n    return False\n')
    (project/'test_app.py').write_text('from app import read\ndef test_read():\n    assert read() == True\n')
    signatures = [_replay_signature(_probe(project, tmp_path/f'probe-{i}', ['test_app.py'], [], 30, Path(sys.executable))) for i in range(2)]
    assert signatures[0] == signatures[1]
    assert _stable_summary('<function read at 0x12>') != _stable_summary('<function write at 0x34>')
