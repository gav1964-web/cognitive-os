"""Native witnesses remain mandatory when an unrelated invalid fault is replaced."""
import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from runtime.feature_quality_challenge import challenge_with_feedback, check_campaign
from runtime.feature_quality_chat import QualityChat
from runtime.feature_workspace import inventory
from runtime.local_inference import LocalInferenceConfig


def setup_case(tmp_path):
    candidate = tmp_path / 'candidate'
    (candidate / 'tests').mkdir(parents=True)
    (candidate / 'engine.py').write_text('def value(x):\n    return x\n')
    body = 'from engine import value\ndef test_first():\n    assert value(1) == 1\n'
    (candidate / 'tests/test_first.py').write_text(body)
    spec = {'tests': [{'path': 'tests/test_first.py', 'content': body}], 'regression_tests': []}
    hashes = inventory(candidate)

    def fault(number):
        return {'id': str(number), 'reason': f'identity at {number}', 'edits': [{
            'path': 'engine.py', 'source_sha256': hashes['engine.py'],
            'replacements': [{'old': 'return x', 'new': f'return 0 if x == {number} else x'}]}],
            'oracle_tests': [{'path': 'tests/test_witness.py', 'content':
                f'from engine import value\ndef test_witness():\n    assert value({number}) == {number}\n'}]}
    return candidate, spec, fault


def test_union_is_rechecked_and_no_valid_survivor_can_be_dropped(tmp_path):
    candidate, spec, fault = setup_case(tmp_path)
    before = inventory(candidate)
    invalid = fault(9)
    invalid['edits'][0]['replacements'][0]['old'] = 'not in source'
    proposals = [{'challenges': [fault(3), invalid, fault(1)]},
                 {'challenges': [fault(4), fault(3), fault(5)]}]
    requests = []

    def transport(messages, *, config):
        requests.append(json.loads(messages[1]['content']))
        return deepcopy(proposals[len(requests) - 1])

    q = QualityChat(transport, tmp_path / 'journal')
    args = dict(candidate=candidate, python=Path(sys.executable), allowed=['engine.py'])
    proposal, checked = challenge_with_feedback(q, LocalInferenceConfig('http://unused', 'fake'),
        {'candidate_sources': []}, work=tmp_path / 'campaign', spec=spec, **args)
    assert checked['status'] == 'needs_specification'
    assert [v['id'] for v in checked['variants']] == ['3', '1', '4', '5']
    assert [v['status'] for v in checked['variants']] == ['survived', 'killed', 'survived', 'survived']
    assert len(requests[1]['retained_valid_challenges']) == 2
    assert len(proposal['challenges']) == 4  # No truncation at the model's three-variant limit.
    retained = json.loads((tmp_path / 'campaign-retained.json').read_text())
    assert retained['candidate_hashes'] == before and not retained['grants_approval']
    assert inventory(candidate) == before
    for number in (3, 4, 5):
        body = f'from engine import value\ndef test_{number}():\n    assert value({number}) == {number}\n'
        name = f'tests/test_{number}.py'
        (candidate / name).write_text(body)
        spec['tests'].append({'path': name, 'content': body})
    # Reuse in a later SpecWriter cycle must re-execute the complete campaign.
    replay = check_campaign(work=tmp_path / 'replay', specification=spec,
                            challenges=proposal['challenges'], **args)
    assert replay['status'] == 'passed' and len(replay['variants']) == 4


@pytest.mark.parametrize('replacement', [[], None])
def test_empty_retry_cannot_turn_retained_success_into_approval(tmp_path, replacement):
    candidate, spec, fault = setup_case(tmp_path)
    invalid = fault(9)
    invalid['edits'][0]['replacements'][0]['old'] = 'absent'
    replies = iter([{'challenges': [fault(1), invalid]}, {'challenges': replacement}])
    q = QualityChat(lambda *args, **kwargs: next(replies), tmp_path / 'journal')
    _, checked = challenge_with_feedback(q, LocalInferenceConfig('http://unused', 'fake'),
        {'candidate_sources': []}, candidate=candidate, work=tmp_path / 'campaign',
        python=Path(sys.executable), spec=spec, allowed=['engine.py'])
    assert checked['status'] == 'inconclusive'
    assert checked['validation_attempts'][0]['variants'][0]['status'] == 'killed'
    assert json.loads((tmp_path / 'campaign-retained.json').read_text())['challenges']


def test_changed_candidate_cannot_inherit_obligations(tmp_path):
    candidate, spec, fault = setup_case(tmp_path)
    proposal = fault(1)

    def transport(*args, **kwargs):
        (candidate / 'engine.py').write_text('def value(x):\n    return 0\n')
        return {'challenges': [proposal]}

    q = QualityChat(transport, tmp_path / 'journal')
    with pytest.raises(ValueError, match='candidate_changed'):
        challenge_with_feedback(q, LocalInferenceConfig('http://unused', 'fake'),
            {'candidate_sources': []}, candidate=candidate, work=tmp_path / 'campaign',
            python=Path(sys.executable), spec=spec, allowed=['engine.py'])


def test_later_inconclusive_check_keeps_prior_obligation_in_journal(tmp_path, monkeypatch):
    candidate, spec, fault = setup_case(tmp_path)
    replies = iter([{'challenges': [fault(3), fault(9)]}, {'challenges': [fault(4)]}])
    states = iter([['survived', 'invalid'], ['invalid', 'killed']])

    def checked(**kwargs):
        return {'status': 'inconclusive', 'candidate_hashes': inventory(candidate),
            'source_unchanged': True, 'variants': [
                {'id': c['id'], 'status': status} for c, status in
                zip(kwargs['challenges'], next(states))]}

    monkeypatch.setattr('runtime.feature_quality_challenge.check_campaign', checked)
    q = QualityChat(lambda *args, **kwargs: next(replies), tmp_path / 'journal')
    proposal, result = challenge_with_feedback(q, LocalInferenceConfig('http://unused', 'fake'),
        {'candidate_sources': []}, candidate=candidate, work=tmp_path / 'campaign',
        python=Path(sys.executable), spec=spec, allowed=['engine.py'])
    assert result['status'] == 'inconclusive'
    assert [c['id'] for c in proposal['challenges']] == ['3', '4']
    receipt = json.loads((tmp_path / 'campaign-retained.json').read_text())
    assert [c['id'] for c in receipt['challenges']] == ['3', '4']
