"""Real subprocess checks distinguish a useful regression from green/setup noise."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

from runtime.feature_spec_witness import RejectedCandidateWitness
from runtime.feature_workspace import inventory, digest
from runtime.feature_quality_chat import QualityChat
from runtime.local_inference import LocalInferenceConfig
from tests.runtime.test_feature_development import project, spec, fake_chat
from tests.runtime.test_feature_quality import augment


def witness(project, tmp_path):
    frozen = spec()['tests']
    expected = inventory(project)
    cfg = LocalInferenceConfig('http://unused', 'fake', provider_label='feature:programmer')
    proposal = fake_chat(project)([], config=cfg)
    patched = b'def display(value):\n    return f"({-value})" if value < 0 else str(value)\n'
    if b'\r\n' in (project / 'engine.py').read_bytes():
        patched = patched.replace(b'\n', b'\r\n')
    candidate = {'proposal': proposal, 'review': {'decision': 'reject'},
        'candidate_hashes': {'engine.py': digest(patched),
            frozen[0]['path']: digest(frozen[0]['content'].encode())}}
    return RejectedCandidateWitness(project=project, expected=expected, candidate=candidate,
        frozen=frozen, allowed=['engine.py'], work=tmp_path / 'witness', python=Path(sys.executable))


def with_test(body):
    value = spec()
    value['tests'].append({'path': 'tests/test_new.py', 'content': body})
    return value


@pytest.mark.parametrize('body,expected_status', [
    ('from engine import display\ndef test_boundary():\n    assert display(0) == "zero"\n', 'witness_found'),
    ('from engine import display\ndef test_green():\n    assert display(3) == "3"\n', 'rejected'),
    ('def test_bad_setup():\n    raise IndexError("fixture exhausted")\n    assert False\n', 'rejected'),
    ('import pytest\n@pytest.fixture\ndef broken():\n    assert False\ndef test_setup(broken):\n    assert True\n', 'rejected'),
])
def test_native_discriminator_requires_assertion_failure(project, tmp_path, body, expected_status):
    gate = witness(project, tmp_path)
    before = inventory(project)
    issues = gate(with_test(body))
    report = json.loads((tmp_path / 'witness/1/report.json').read_text())
    assert report['status'] == expected_status
    assert bool(issues) == (expected_status == 'rejected')
    assert not report['grants_approval'] and inventory(project) == before


@pytest.mark.parametrize('changed', ['source', 'candidate', 'frozen'])
def test_stale_bindings_never_run_tests(project, tmp_path, changed):
    gate = witness(project, tmp_path)
    value = with_test('def test_new():\n    assert False\n')
    if changed == 'source':
        (project / 'engine.py').write_text('# changed\n')
    elif changed == 'candidate':
        gate.candidate['candidate_hashes']['engine.py'] = 'wrong'
    else:
        value['tests'][0]['content'] += '# changed\n'
    with pytest.raises(ValueError, match='quality_witness_'):
        gate(value)
    assert not (tmp_path / 'witness/1/checks').exists()


def test_green_draft_returns_to_writer_before_paid_audit(project, tmp_path):
    calls = []
    green = augment('spec_writer', with_test('from engine import display\ndef test_boundary():\n    assert display(0) == "0"\n'))
    red = deepcopy(green)
    red['tests'][-1]['content'] = red['tests'][-1]['content'].replace('== "0"', '== "zero"')

    def chat(messages, *, config):
        role = config.provider_label
        calls.append(role)
        if role == 'quality:spec_auditor':
            return {'decision': 'approve'}
        if len(calls) == 1:
            return green
        payload = json.loads(messages[1]['content'])
        assert payload['quality_contract_feedback']['issues'][0]['rejected_candidate_witness']['counts']['passed'] == 1
        return red

    q = QualityChat(chat, tmp_path / 'quality')
    q.spec_witness = witness(project, tmp_path)
    q.frozen = spec()['tests']
    value = q([{'role': 'system', 'content': 'spec'}, {'role': 'user', 'content': json.dumps({
        'goal': 'zero labels', 'sources': [], 'artifacts': {'architect': {}}})}],
        config=LocalInferenceConfig('http://unused', 'fake', provider_label='feature:spec_writer'))
    assert value == red
    assert calls == ['feature:spec_writer', 'feature:spec_writer', 'quality:spec_auditor']
