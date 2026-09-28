"""Data observations execute model code in copies and reject mutations."""
import sys

import pytest

from runtime.feature_data_probe import run_data_probe
from tests.runtime.test_feature_development import project


@pytest.mark.parametrize('mutation', [False, True])
def test_probe_observes_real_input_in_copy(project, tmp_path, mutation):
    (project / 'data.bin').write_bytes(b'\x02\x03')
    code = 'from engine import display\np = PROJECT / INPUTS[0]\n'
    code += 'RESULT = {"result": display(p.read_bytes()[0])}\n'
    if mutation: code += 'p.write_bytes(b"changed")\n'
    result = run_data_probe(project=project, work=tmp_path / 'probe',
        python=sys.executable, inputs=['data.bin'], proposal={'code': code})
    assert result['status'] == ('blocked' if mutation else 'observed')
    assert result['observations'] == {'result': '2'}
    assert (project / 'data.bin').read_bytes() == b'\x02\x03'


def test_probe_preserves_unicode_through_non_utf8_child_stdout(project, tmp_path):
    (project / 'data.bin').write_bytes(b'input')
    code = ('import sys\nsys.stdout.reconfigure(encoding="ascii")\n'
            'RESULT = {"город": "Курск", "symbol": "🙂"}\n')
    result = run_data_probe(project=project, work=tmp_path / 'unicode',
        python=sys.executable, inputs=['data.bin'], proposal={'code': code})
    assert result['status'] == 'observed'
    assert result['observations'] == {'город': 'Курск', 'symbol': '🙂'}
    assert result['source_unchanged'] and result['inputs_unchanged']
