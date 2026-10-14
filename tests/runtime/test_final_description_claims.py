"""Final assertions are separately bound; a README is never code evidence by itself."""
from copy import deepcopy
import hashlib
import json

import pytest

from runtime.single_claim_review import prepare_claim_review, run_claim_review
from runtime.claim_review_proposals import checked_proposal, attach_proposals
from runtime.claim_review_reporting import inspect_review
from runtime.narrow_type_evidence_binding import content_digest
from runtime.product_context import make_product_context
from runtime.project_description import describe_project, render_description
from tests.runtime.test_lean_claim_review import saved_report


@pytest.fixture
def report(tmp_path):
    result = saved_report(tmp_path, 'def run(x):\n    return x + 1\n', 'Adds one.')
    result['description']['purpose']['text'] = 'Adds two.'
    return result


def refutation(job):
    citation = [{'source_id': 's1', 'quote': 'return x + 1'}]
    return {'parts': [{'text': job['claim']['text'], 'verdict': 'refuted',
                       'reason': 'Adds one, not two.', 'citations': citation}],
            'coverage': {'scope': {'status': 'shown', 'reason': 'Full source.', 'citations': citation},
                         'bindings': {'status': 'not_applicable', 'reason': 'Direct arithmetic.', 'citations': []}},
            'proposed_text': None}


def test_final_namespace_reviews_new_editor_error_and_does_not_close_draft_task(report):
    draft = prepare_claim_review(report, 'purpose')
    job = prepare_claim_review(report, 'purpose', claim_namespace='final')
    assert draft['original_claim']['text'] == 'Adds one.'
    assert job['original_claim']['text'] == 'Adds two.'
    assert draft['digest'] != job['digest']
    receipt = run_claim_review(job, chat=lambda *a, **k: refutation(job))
    assert receipt['status'] == 'reviewed' and receipt['result']['verdict'] == 'refuted'
    checked_proposal(receipt, report=report)
    assert inspect_review(receipt)['claim_namespace'] == 'final'
    audit = {'source_report_digest': content_digest(report), 'review_tasks': [
        {'claim_id': 'purpose'}, {'claim_id': 'purpose', 'claim_namespace': 'final'}]}
    attached = attach_proposals(audit, [receipt])
    assert attached['review_tasks'][0]['proposal_digests'] == []
    assert attached['review_tasks'][1]['proposal_digests'] == [receipt['digest']]


def test_rehashed_namespace_swap_cannot_bind_draft_to_final_report(report):
    job = prepare_claim_review(report, 'purpose')
    receipt = run_claim_review(job, chat=lambda *a, **k: refutation(job))
    receipt['job']['claim_namespace'] = 'final'
    receipt['job']['digest'] = content_digest({k: v for k, v in receipt['job'].items() if k != 'digest'})
    receipt['digest'] = content_digest({k: v for k, v in receipt.items() if k != 'digest'})
    with pytest.raises(ValueError, match='wrong_namespace_or_claim'):
        checked_proposal(receipt, report=report)


@pytest.mark.parametrize('version', [1, 2, 3])
def test_legacy_contracts_do_not_acquire_final_namespace(report, version):
    with pytest.raises(ValueError, match='final_requires_v4'):
        prepare_claim_review(report, 'purpose', claim_namespace='final', review_version=version)


def test_failed_or_stale_reports_cannot_prepare_final_claims(report, tmp_path):
    report['status'] = 'failed'
    with pytest.raises(ValueError, match='final_description_required'):
        prepare_claim_review(report, 'purpose', claim_namespace='final')
    report['status'] = 'described'
    (tmp_path / 'example.py').write_text('changed', encoding='utf-8')
    with pytest.raises(ValueError, match='stale_sources'):
        prepare_claim_review(report, 'purpose', claim_namespace='final')


def test_doc_only_claim_is_marked_and_rejected_despite_forged_grounding(tmp_path):
    path = tmp_path / 'README.md'
    path.write_text('# Example\nAdds two.\n', encoding='utf-8')
    claim = {'text': 'Adds two.', 'evidence_ids': ['s1']}
    answer = {'purpose': claim, 'scenarios': [claim], 'data_flow': [claim], 'unknowns': [], 'confidence': 'high'}
    def chat(messages, *, config):
        payload = json.loads(messages[1]['content'])
        if 'draft' not in payload:
            return answer
        return {'description': answer, 'corrections': [], 'claim_reviews': [
            {'claim_id': c['id'], 'action': 'retained', 'reason': 'Documented.', 'evidence_ids': ['s1']}
            for c in payload['draft_claims']]}
    result = describe_project(tmp_path, chat=chat)
    assert result['status'] == 'described'
    assert result['claim_grounding']['claims'][0]['status'] == 'documentation_only'
    result['claim_grounding']['claims'][0]['status'] = 'implementation_cited'
    assert 'Подтверждение реализацией не установлено.' in render_description(result)
    with pytest.raises(ValueError, match='implementation_evidence_required'):
        make_product_context(result, accepted_claim_ids=['purpose'], reviewer='fixture')


def test_code_citation_is_not_automatic_semantic_confirmation(report):
    # The intentionally false final assertion cites real code. A structural guard
    # cannot infer its truth: the caller still supplies explicit reviewed IDs.
    with pytest.raises(ValueError, match='explicit_claim_review'):
        make_product_context(report, accepted_claim_ids=[], reviewer='fixture')
    packet = make_product_context(report, accepted_claim_ids=['purpose'], reviewer='fixture-attestation')
    assert packet['review_authority'] == 'caller_attestation_not_independent_certification'
    assert packet['execution_authorized'] is False
