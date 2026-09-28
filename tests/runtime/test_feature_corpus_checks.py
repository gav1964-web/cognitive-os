"""Binary inputs are opt-in, hash-bound, and tested in separate source copies."""
import sys
import json
from pathlib import Path

import pytest

from runtime.feature_corpus_checks import input_inventory, run_corpus_checks
from runtime.feature_workspace import inventory
from tests.runtime.test_feature_development import project, fake_chat, run


@pytest.mark.parametrize('regression', [False, True])
def test_existing_corpus_checks_preserve_target_and_compare(project, tmp_path, regression):
    (project / 'sample.bin').write_bytes(b'\x00\x02')
    (project / 'tests/test_binary.py').write_text(
        'from pathlib import Path\nfrom engine import display\n'
        'def test_input():\n'
        '    value = Path("sample.bin").read_bytes()[1]\n'
        + ('    assert display(-value) == "-2"\n' if regression else
           '    assert display(value) == "2"\n'), encoding='utf-8')
    before = inventory(project)
    candidate = run(project, tmp_path, chat=fake_chat(project))
    assert candidate['status'] == 'verified'
    result = run_corpus_checks(project=project, checkpoint=tmp_path / 'run',
        work=tmp_path / 'corpus', python=Path(sys.executable), inputs=['sample.bin'],
        targets=['tests/test_binary.py'])
    assert result['status'] == ('blocked' if regression else 'passed')
    assert bool(result['regressions']) == regression
    assert result['checks']['baseline']['counts']['passed'] == 1
    assert result['source_unchanged'] and result['original_inputs_unchanged']
    assert inventory(project) == before
    assert (project / 'sample.bin').read_bytes() == b'\x00\x02'


@pytest.mark.parametrize('names', [[], ['../outside.bin'], ['engine.py'], ['.env'], ['sample.bin'] * 2])
def test_inputs_reject_escape_source_and_secrets(project, names):
    with pytest.raises(ValueError):
        input_inventory(project, names, inventory(project))


@pytest.mark.parametrize('stale', [None, 'source', 'input', 'targets'])
def test_reused_baseline_requires_exact_bindings(project, tmp_path, stale):
    (project / 'sample.bin').write_bytes(b'\x02')
    (project / 'tests/test_binary.py').write_text(
        'from pathlib import Path\ndef test_input():\n'
        '    assert Path("sample.bin").read_bytes() == bytes([2])\n')
    run(project, tmp_path, chat=fake_chat(project))
    args = dict(project=project, checkpoint=tmp_path / 'run', python=Path(sys.executable),
                inputs=['sample.bin'], targets=['tests/test_binary.py'])
    first = run_corpus_checks(**args, work=tmp_path / 'first')
    # A previous successful check of exactly this baseline, not the new patch.
    receipt = {**first, 'candidate_hashes': {},
               'checks': {'candidate': first['checks']['baseline']}}
    if stale == 'source': receipt['source_hashes'] = {}
    if stale == 'input': receipt['input_hashes'] = {'sample.bin': 'stale'}
    if stale == 'targets': receipt['targets'] = ['tests/test_other.py']
    path = tmp_path / 'prior.json'; path.write_text(json.dumps(receipt))
    if stale:
        with pytest.raises(ValueError, match='baseline_receipt_mismatch'):
            run_corpus_checks(**args, work=tmp_path / 'reuse', baseline_receipt=path)
    else:
        result = run_corpus_checks(**args, work=tmp_path / 'reuse', baseline_receipt=path)
        assert result['status'] == 'passed'
        assert result['baseline_reused_from']['path'] == str(path.resolve())
        assert not (tmp_path / 'reuse/baseline').exists()
