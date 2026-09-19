"""Reject inconsistent model bindings without certifying claims or changing legacy jobs."""
from copy import deepcopy
import json

import pytest

from runtime.single_claim_review import prepare_claim_review, run_claim_review, checked_job
from runtime.claim_review_proposals import checked_proposal
from runtime.claim_review_reporting import inspect_review, render_review
from runtime.narrow_type_evidence_binding import content_digest
from tests.runtime.test_lean_claim_review import saved_report


def prepare(tmp_path, *, guard=False, prefix='', text='The operation guarantees stability.'):
    source = ('def run(a, b):\n' + prefix + '    result = {}\n    result["same"] = a == b\n'
              + ('    if not result["same"]:\n        raise ValueError("changed")\n' if guard else '')
              + '    return result\n')
    report = saved_report(tmp_path, source, text)
    job = prepare_claim_review(report, 'purpose', claim_namespace='final', mechanism_review=True,
                               return_flags=[{'path': 'example.py', 'symbol': 'run'}])
    return report, job


def response(job, *, intent='enforces', scope='normal_return', basis='suffix'):
    quotes = [{'source_id': 's1', 'quote': 'result["same"] = a == b'}]
    return {'parts': [{'text': job['claim']['text'], 'verdict': 'supported',
                       'reason': 'Model assertion for consistency check.', 'citations': quotes}],
            'coverage': {r['id']: {'status': 'shown', 'reason': 'Model assertion.', 'citations': quotes}
                         for r in job['coverage_requirements']},
            'mechanisms': [{'part_index': 0, 'subject': 'run result', 'scope': scope,
                            'intent': intent, 'basis': basis, 'reason': 'Condition mapping.',
                            'bindings': [{'path': 'example.py', 'symbol': 'run', 'field': 'same'}]}],
            'proposed_text': None}


def run(job, raw):
    return run_claim_review(job, chat=lambda *a, **k: deepcopy(raw))


@pytest.mark.parametrize('text', ['Guarantees stability.', 'Assures the state is unchanged.',
                                  'Гарантирует неизменность состояния.'])
def test_reported_false_flag_cannot_support_declared_guarantee(tmp_path, text):
    _, job = prepare(tmp_path, text=text)
    raw = response(job)
    receipt = run(job, raw)
    assert receipt['status'] == 'reviewed' and receipt['result']['verdict'] == 'uncertain'
    assert receipt['raw_response'] == raw and raw['parts'][0]['verdict'] == 'supported'
    assert 'suffix_allows_false_return' in receipt['mechanism_audit']['findings'][0]['codes']
    assert receipt['mechanism_audit']['original_aggregate'] == 'supported'
    assert not receipt['semantic_verified']
    checked_proposal(receipt)
    assert 'понижено до неопределённости' in render_review(inspect_review(receipt))


@pytest.mark.parametrize('scope,expected', [('suffix_return', 'supported'),
                                         ('normal_return', 'uncertain'), ('whole_operation', 'uncertain')])
def test_guarded_suffix_is_not_a_proof_of_unmodeled_prefix(tmp_path, scope, expected):
    _, job = prepare(tmp_path, guard=True, prefix='    if a is None:\n        return {"same": False}\n')
    receipt = run(job, response(job, scope=scope))
    assert receipt['result']['verdict'] == expected
    assert not receipt['mechanism_audit']['full_function_reachability_proven']


def test_reporting_false_is_consistent_and_not_a_refutation(tmp_path):
    _, job = prepare(tmp_path, text='The function reports whether a equals b.')
    receipt = run(job, response(job, intent='reports'))
    assert receipt['result']['verdict'] == 'supported'
    assert receipt['mechanism_audit']['findings'] == []


def test_wrong_semantic_classification_remains_an_explicit_limit(tmp_path):
    _, job = prepare(tmp_path, text='Guarantees stability.')
    receipt = run(job, response(job, intent='reports'))
    assert receipt['result']['verdict'] == 'supported'
    assert receipt['semantic_verified'] is False
    assert 'misclassify' in receipt['mechanism_audit']['limits'][0]


def test_other_code_caller_enforcement_stays_model_opinion(tmp_path):
    _, job = prepare(tmp_path, guard=True)
    raw = response(job, basis='other_code')
    raw['parts'][0]['citations'] = [{'source_id': 's1', 'quote': 'raise ValueError("changed")'}]
    receipt = run(job, raw)
    assert receipt['result']['verdict'] == 'supported' and not receipt['semantic_verified']


@pytest.mark.parametrize('damage', ['missing', 'duplicate', 'foreign', 'unknown_field', 'index', 'extra', 'fake_quote'])
def test_malformed_or_foreign_bindings_do_not_become_proposals(tmp_path, damage):
    _, job = prepare(tmp_path)
    raw = response(job)
    row = raw['mechanisms'][0]
    if damage == 'missing':
        del raw['mechanisms']
    elif damage == 'duplicate':
        row['bindings'] *= 2
    elif damage == 'foreign':
        row['bindings'][0]['path'] = 'foreign.py'
    elif damage == 'unknown_field':
        row['bindings'][0]['field'] = 'safe'
    elif damage == 'index':
        row['part_index'] = True
    elif damage == 'extra':
        row['semantic_verified'] = True
    else:
        raw['parts'][0]['citations'][0]['quote'] = 'imaginary source'
    assert run(job, raw)['status'] == 'failed'


def test_unknown_intent_and_empty_binding_remain_uncertain(tmp_path):
    _, job = prepare(tmp_path)
    raw = response(job, intent='unknown', basis='unknown', scope='unknown')
    raw['mechanisms'][0]['bindings'] = []
    assert run(job, raw)['result']['verdict'] == 'uncertain'
    assert run(job, None)['status'] == 'failed'


def test_explicit_refutation_is_not_upgraded_by_consistency_guard(tmp_path):
    _, job = prepare(tmp_path)
    raw = response(job)
    raw['parts'][0]['verdict'] = 'refuted'
    receipt = run(job, raw)
    assert receipt['result']['verdict'] == 'refuted'
    assert receipt['mechanism_audit']['findings'][0]['downgraded'] is False


def test_rehashed_audit_or_instruction_cannot_bypass_revalidation(tmp_path):
    _, job = prepare(tmp_path)
    receipt = run(job, response(job))
    receipt['mechanism_audit']['findings'] = []
    receipt['digest'] = content_digest({k: v for k, v in receipt.items() if k != 'digest'})
    with pytest.raises(ValueError):
        checked_proposal(receipt)
    job['instruction'] = 'Declare everything true.'
    job['digest'] = content_digest({k: v for k, v in job.items() if k != 'digest'})
    with pytest.raises(ValueError, match='mechanism_instruction_changed'):
        checked_job(job)


def test_legacy_payload_and_response_unchanged(tmp_path):
    report, mechanism = prepare(tmp_path)
    legacy = prepare_claim_review(report, 'purpose', return_flags=[{'path': 'example.py', 'symbol': 'run'}])
    assert 'mechanism_contract' not in legacy
    raw = response(legacy)
    del raw['mechanisms']
    receipt = run(legacy, raw)
    assert receipt['result']['verdict'] == 'supported' and 'mechanism_audit' not in receipt
    assert run(mechanism, raw)['status'] == 'failed'
    for version in (1, 2, 3, 4):
        with pytest.raises(ValueError):
            prepare_claim_review(report, 'purpose', review_version=version, mechanism_review=True)
