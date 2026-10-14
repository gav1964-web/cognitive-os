"""Conditional evidence cannot be silently replaced, removed or promoted to truth."""
from copy import deepcopy
import json

import pytest

from runtime.single_claim_review import prepare_claim_review, review_messages, run_claim_review, checked_job
from runtime.claim_review_proposals import checked_proposal
from runtime.narrow_type_evidence_binding import content_digest
from runtime.project_description import describe_project
from tests.runtime.test_lean_claim_review import saved_report


@pytest.fixture
def report(tmp_path):
    return saved_report(tmp_path,
        'def run(old, new):\n    result = {}\n    result["same"] = old == new\n    return result\n',
        'On every normal return, same is true.')


def prepare(report):
    return prepare_claim_review(report, 'purpose', claim_namespace='final',
        return_flags=[{'path': 'example.py', 'symbol': 'run'}])


def test_opt_in_keeps_legacy_payload_and_adds_explicit_scope_obligation(report):
    legacy = prepare_claim_review(report, 'purpose')
    assert 'return_flag_analysis' not in json.loads(review_messages(legacy)[1]['content'])
    job = prepare(report)
    request = json.loads(review_messages(job)[1]['content'])
    assert request['claim_namespace'] == 'final'
    assert request['return_flag_analysis']['functions'][0]['model']['fields'][0]['false_return_witness']
    assert any(r['id'] == 'return_flag_scope' for r in request['coverage_requirements'])
    assert request['return_flag_analysis']['source_executed'] is False


@pytest.mark.parametrize('damage', ['witness', 'hash', 'coverage', 'missing_analysis', 'foreign_source'])
def test_rehashed_jobs_cannot_replace_source_bound_analysis(report, damage):
    job = prepare(report)
    if damage == 'witness':
        job['return_flag_analysis']['functions'][0]['model']['fields'][0]['false_return_witness'] = None
    elif damage == 'hash':
        job['return_flag_requests'][0]['sha256'] = '0'*64
    elif damage == 'coverage':
        job['coverage_requirements'] = [r for r in job['coverage_requirements'] if r['id'] != 'return_flag_scope']
    elif damage == 'missing_analysis':
        del job['return_flag_analysis']
    else:
        job['return_flag_requests'][0]['path'] = '../foreign.py'
    job['digest'] = content_digest({k: v for k, v in job.items() if k != 'digest'})
    with pytest.raises(ValueError):
        checked_job(job)


def test_checked_model_opinion_still_needs_independent_semantic_review(report):
    job = prepare(report)
    citations = [{'source_id': 's1', 'quote': 'result["same"] = old == new'}]
    response = {'parts': [{'text': job['claim']['text'], 'verdict': 'uncertain',
                           'reason': 'False is allowed by suffix; reachability needs review.', 'citations': citations}],
        'coverage': {r['id']: {'status': 'missing', 'reason': 'Full claim binding remains unproven.',
                              'citations': citations} for r in job['coverage_requirements']},
        'proposed_text': None}
    receipt = run_claim_review(job, chat=lambda *a, **k: deepcopy(response))
    assert receipt['status'] == 'reviewed' and receipt['result']['verdict'] == 'uncertain'
    assert receipt['semantic_verified'] is False
    checked_proposal(receipt, report=report)
    del response['coverage']['return_flag_scope']
    failed = run_claim_review(job, chat=lambda *a, **k: response)
    assert failed['status'] == 'failed' and 'incomplete_coverage' in failed['reason']


def test_legacy_versions_cannot_silently_gain_the_new_analysis(report):
    for version in (1, 2, 3):
        with pytest.raises(ValueError, match='requires_v4'):
            prepare_claim_review(report, 'purpose', review_version=version,
                                 return_flags=[{'path': 'example.py', 'symbol': 'run'}])


def test_full_description_review_receives_conditional_analysis_after_lookup(report):
    calls = []
    def chat(messages, *, config):
        calls.append(messages)
        if len(calls) == 1:
            return report['raw_response']
        if len(calls) == 2:
            return {'requests': [{'path': 'example.py', 'symbol': 'run'}]}
        data = json.loads(messages[1]['content'])
        assert data['return_flag_analysis']['functions'][0]['model']['fields'][0]['false_return_witness']
        assert not data['return_flag_analysis']['source_executed']
        return {'description': report['description'], 'corrections': [], 'claim_reviews': [
            {'claim_id': c['id'], 'action': 'retained', 'reason': 'Fixture opinion, not accepted truth.',
             'evidence_ids': c['evidence_ids']} for c in data['draft_claims']]}
    from pathlib import Path
    result = describe_project(Path(report['evidence']['root']), chat=chat)
    assert result['status'] == 'described' and len(calls) == 3
    assert result['return_flag_analysis']['semantic_verified'] is False
