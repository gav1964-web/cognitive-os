"""Deliver model checkpoints as one verified transaction, with no new code generation."""
import json
import sys
from pathlib import Path

import pytest

from runtime.feature_delivery import deliver_feature
from runtime.feature_corpus_checks import run_corpus_checks
from runtime.feature_workspace import digest, inventory
from tests.runtime.test_feature_development import project, fake_chat, run


def two_stages(project, tmp_path):
    first = tmp_path / 'first'
    assert run(project, first, chat=fake_chat(project))['status'] == 'verified'
    baseline = first / 'run/attempt-1/project'
    delegate = fake_chat(baseline)
    def chat(messages, *, config):
        role = config.provider_label
        if role == 'feature:spec_writer':
            return {'status': 'ready', 'acceptance': ['zero label'], 'limitations': ['fixture only'],
                'environment': {}, 'tests': [{'path': 'tests/test_zero.py', 'content':
                    'from engine import display\ndef test_zero():\n    assert display(0) == "zero"\n'}],
                'regression_tests': ['tests/test_existing.py', 'tests/test_labels.py']}
        if role == 'feature:programmer':
            return {'status': 'ready', 'edits': [{'path': 'engine.py',
                'source_sha256': digest((baseline / 'engine.py').read_bytes()),
                'replacements': [{'old': 'else str(value)',
                                  'new': 'else "zero" if value == 0 else str(value)'}]}]}
        return delegate(messages, config=config)
    second = tmp_path / 'second'
    assert run(baseline, second, chat=chat)['status'] == 'verified'
    return [first / 'run', second / 'run']


@pytest.mark.parametrize('apply', [False, True])
def test_two_stage_delivery_preserves_exact_model_bytes(project, tmp_path, apply):
    original = inventory(project)
    checkpoints = two_stages(project, tmp_path)
    result = deliver_feature(project=project, checkpoints=checkpoints,
        work=tmp_path / 'delivery', python=Path(sys.executable), apply_source=apply)
    assert result['status'] == ('installed' if apply else 'verified')
    assert result['verification']['counts']['passed'] == 3
    assert inventory(project) == (result['final_hashes'] if apply else original)
    if apply:
        assert (project / 'engine.py').read_bytes() == (
            checkpoints[-1] / 'attempt-1/project/engine.py').read_bytes()
        assert (tmp_path / 'delivery/backup/engine.py').is_file()


@pytest.mark.parametrize('broken', ['review', 'order', 'candidate', 'source'])
def test_delivery_rejects_broken_chain_without_target_write(project, tmp_path, broken):
    checkpoints = two_stages(project, tmp_path)
    if broken == 'review':
        path = checkpoints[-1] / 'reviewer.json'
        data = json.loads(path.read_text()); data['decision'] = 'reject'
        path.write_text(json.dumps(data))
    elif broken == 'order': checkpoints.reverse()
    elif broken == 'candidate':
        path = checkpoints[-1] / 'proposal-1.json'
        data = json.loads(path.read_text())
        data['edits'][0]['replacements'][0]['new'] = 'else "unreviewed"'
        path.write_text(json.dumps(data))
    else: (project / 'engine.py').write_text('# concurrent work\n')
    before = inventory(project)
    with pytest.raises(ValueError):
        deliver_feature(project=project, checkpoints=checkpoints,
            work=tmp_path / 'delivery', python=Path(sys.executable), apply_source=True)
    assert inventory(project) == before


@pytest.mark.parametrize('stale', [False, True])
def test_corpus_receipt_binds_final_tree_and_original_inputs(project, tmp_path, stale):
    checkpoints = two_stages(project, tmp_path)
    baseline = checkpoints[0] / 'attempt-1/project'
    for root in (project, baseline):
        (root / 'sample.bin').write_bytes(b'input')
    corpus = tmp_path / 'corpus'
    assert run_corpus_checks(project=baseline, checkpoint=checkpoints[-1], work=corpus,
        python=Path(sys.executable), inputs=['sample.bin'],
        targets=['tests/test_existing.py'])['status'] == 'passed'
    before = inventory(project)
    if stale: (project / 'sample.bin').write_bytes(b'changed')
    kwargs = dict(project=project, checkpoints=checkpoints, work=tmp_path / 'delivery',
        python=Path(sys.executable), corpus_receipt=corpus / 'report.json')
    if stale:
        with pytest.raises(ValueError, match='corpus_not_bound'):
            deliver_feature(**kwargs, apply_source=True)
        assert inventory(project) == before
    else:
        result = deliver_feature(**kwargs)
        assert result['status'] == 'verified' and result['corpus_receipt']['sha256']
