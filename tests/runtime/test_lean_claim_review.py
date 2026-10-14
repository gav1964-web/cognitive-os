"""V3 contracts and explicit historical replay, not semantic certification."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from runtime.single_claim_review import prepare_claim_review, run_claim_review
from runtime.claim_review_replay import replay_as_v3
from runtime.claim_review_proposals import checked_proposal
from runtime.claim_review_reporting import inspect_review, render_review
from runtime.narrow_type_evidence_binding import content_digest


def saved_report(folder, source, text):
    folder.mkdir(exist_ok=True)
    file = folder / 'example.py'
    file.write_bytes(source.encode())
    claim = {'text': text, 'evidence_ids': ['s1']}
    draft = {'purpose': claim, 'scenarios': [claim], 'data_flow': [claim], 'unknowns': [], 'confidence': 'medium'}
    return {'status': 'described', 'raw_response': draft, 'description': deepcopy(draft),
            'evidence': {'root': str(folder), 'sources': [{'id': 's1', 'path': 'example.py',
                'excerpt': source, 'sha256': hashlib.sha256(file.read_bytes()).hexdigest()}]}}


@pytest.fixture
def sample(tmp_path):
    report = saved_report(tmp_path, 'def f(x):\n    if x is None:\n        return "empty"\n    return str(x)\n',
                          'Returns text. Always calls str(x).')
    job = prepare_claim_review(report, 'scenarios.0', review_version=3)
    q = [{'source_id': 's1', 'quote': 'return str(x)'}]
    response = {'parts': [
        {'text': 'Returns text. ', 'verdict': 'supported', 'reason': 'Returns text.', 'citations': q},
        {'text': 'Always calls str(x).', 'verdict': 'refuted', 'reason': 'None returns early.',
         'citations': [{'source_id': 's1', 'quote': 'if x is None:\n        return "empty"'}]}],
        'coverage': {'scope': {'status': 'shown', 'reason': 'Full body.', 'citations': q},
                     'bindings': {'status': 'not_applicable', 'reason': 'Direct function claim.', 'citations': []}},
        'proposed_text': None}
    return report, job, response


def run(job, response):
    return run_claim_review(job, chat=lambda *a, **k: response)


def test_v3_derives_refutation_without_asking_for_overall_fields(sample):
    _, job, response = sample
    r = run(job, response)
    assert r['status'] == 'reviewed' and r['result']['verdict'] == 'refuted'
    assert r['result']['model_verdict'] is None
    assert r['raw_response'] == response and 'citations' not in r['raw_response']
    assert not r['semantic_verified']
    checked_proposal(r)
    report = inspect_review(r)
    assert report['model_verdict'] is None and report['derived_assessment']
    assert 'общий вердикт рассчитывает код' in render_review(report)


@pytest.mark.parametrize('status,expected', [('missing', 'uncertain'), ('contradicted', 'refuted'), ('shown', 'supported')])
def test_context_distinguishes_unknown_from_visible_contradiction(sample, status, expected):
    _, job, response = sample
    response['parts'][1]['verdict'] = 'supported'
    response['coverage']['bindings'] = {'status': status, 'reason': 'Assessment under test.',
                                        'citations': response['parts'][1]['citations']}
    assert run(job, response)['result']['verdict'] == expected


@pytest.mark.parametrize('damage', ['missing_part', 'fake_quote', 'extra_overall', 'unknown_coverage', 'uncited_contradiction'])
def test_invalid_v3_never_becomes_a_proposal(sample, damage):
    _, job, response = sample
    if damage == 'missing_part':
        response['parts'].pop()
    elif damage == 'fake_quote':
        response['parts'][1]['citations'][0]['quote'] = 'not present in the code'
    elif damage == 'extra_overall':
        response['verdict'] = 'supported'
    elif damage == 'unknown_coverage':
        response['coverage']['invented'] = response['coverage'].pop('bindings')
    else:
        response['coverage']['bindings'].update(status='contradicted', citations=[])
    assert run(job, response)['status'] == 'failed'


def test_rehashed_aggregate_cannot_bypass_derived_verdict(sample):
    _, job, response = sample
    r = run(job, response)
    r['result']['verdict'] = 'supported'
    r['digest'] = content_digest({k: v for k, v in r.items() if k != 'digest'})
    with pytest.raises(ValueError, match='result_changed'):
        checked_proposal(r)


def test_saved_v2_failures_stay_failed_and_projection_is_not_a_proposal(tmp_path):
    folder = Path(__file__).resolve().parents[1] / 'fixtures/project_description'
    cases = json.loads((folder / 'obligation_cases.json').read_text(encoding='utf-8'))['cases']
    samples = json.loads((folder / 'v2_failed_samples.json').read_text(encoding='utf-8'))['samples']
    for case, sample in zip(cases, samples):
        report = saved_report(tmp_path / case['id'], case['source'], case['claim'])
        job = prepare_claim_review(report, 'scenarios.0', review_version=2)
        receipt = run(job, sample['response'])
        before = deepcopy(receipt)
        assert receipt['status'] == 'failed'
        projected = replay_as_v3(receipt)
        assert projected['status'] == 'validated_projection' and projected['model_calls'] == 0
        assert not projected['admissible_model_proposal'] and receipt == before
        with pytest.raises(ValueError):
            checked_proposal(projected)


def test_replay_does_not_silently_discard_duplicate_or_mismatched_coverage(tmp_path):
    folder = Path(__file__).resolve().parents[1] / 'fixtures/project_description'
    case = json.loads((folder / 'obligation_cases.json').read_text(encoding='utf-8'))['cases'][0]
    raw = json.loads((folder / 'v2_failed_samples.json').read_text(encoding='utf-8'))['samples'][0]['response']
    report = saved_report(tmp_path, case['source'], case['claim'])
    raw['coverage']['scope']['id'] = 'other'
    receipt = run(prepare_claim_review(report, 'scenarios.0', review_version=2), raw)
    with pytest.raises(ValueError, match='key_mismatch'):
        replay_as_v3(receipt)
