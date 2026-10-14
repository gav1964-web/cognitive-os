"""Contract regressions with authored responses, not model quality scores."""
from copy import deepcopy
import hashlib
import json

import pytest

from runtime.single_claim_review import prepare_claim_review, run_claim_review, review_messages
from runtime.claim_review_proposals import checked_proposal, attach_proposals
from runtime.description_offline_review import audit_saved_description
from runtime.claim_review_decisions import record_review_decision, checked_decisions
from runtime.product_context import make_product_context, checked_product_context
from runtime.narrow_type_evidence_binding import content_digest
from runtime.upstream_role_handoff import frame_analysis
from runtime.architecture_decision_builder import build_architecture_decision
from runtime.technical_spec_builder import build_technical_spec


@pytest.fixture
def prepared(tmp_path):
    source = 'def read(value):\n    if value is None:\n        return "empty"\n    return str(value)\n'
    (tmp_path / 'core.py').write_text(source, encoding='utf-8')
    claim = {'text': 'Returns a string. Always calls str(value).', 'evidence_ids': ['s1']}
    draft = {'purpose': claim, 'scenarios': [deepcopy(claim)], 'data_flow': [deepcopy(claim)],
             'unknowns': [], 'confidence': 'medium'}
    report = {'status': 'described', 'raw_response': draft, 'description': deepcopy(draft),
              'evidence': {'root': str(tmp_path), 'sources': [{'id': 's1', 'path': 'core.py',
                  'sha256': hashlib.sha256((tmp_path / 'core.py').read_bytes()).hexdigest(), 'excerpt': source,
                  'authority': 'source_excerpt', 'truncated': False}]}}
    return report, prepare_claim_review(report, 'scenarios.0', review_version=2)


def reply(job):
    quote = [{'source_id': 's1', 'quote': 'return str(value)'}]
    return {'verdict': 'supported', 'reason': 'A branch exists.', 'citations': quote,
            'proposed_text': 'Returns a string; handles None separately.',
            'parts': [{'text': text, 'verdict': 'supported', 'reason': 'Code evidence.',
                       'citations': deepcopy(quote), 'counterexamples': []}
                      for text in ('Returns a string. ', 'Always calls str(value).')],
            'coverage': [{'id': row['id'], 'status': 'shown', 'reason': 'Visible function body.',
                          'citations': deepcopy(quote)} for row in job['coverage_requirements']]}


def run(job, response):
    def chat(messages, *, config):
        assert not config.fallbacks and config.max_output_tokens == 3200
        assert json.loads(messages[1]['content'])['coverage_requirements'] == job['coverage_requirements']
        return response
    return run_claim_review(job, chat=chat)


def test_counterexample_overrides_supported_and_preserves_raw(prepared):
    _, job = prepared
    response = reply(job)
    response['parts'][1]['counterexamples'] = [{'source_id': 's1',
        'quote': 'if value is None:\n        return "empty"'}]
    result = run(job, response)
    assert result['status'] == 'reviewed'
    assert result['raw_response'] == response
    assert result['result']['verdict'] == 'refuted'
    assert result['result']['model_verdict'] == 'supported'
    assert result['aggregation']['model_verdict_overridden']
    assert not result['semantic_verified']
    checked_proposal(result)


@pytest.mark.parametrize('kind', ['part', 'coverage'])
def test_uncertainty_cannot_be_promoted_to_supported(prepared, kind):
    _, job = prepared
    response = reply(job)
    if kind == 'part':
        response['parts'][1].update(verdict='uncertain', citations=[])
    else:
        response['coverage'][1].update(status='missing', citations=[])
    result = run(job, response)
    assert result['status'] == 'reviewed' and result['result']['verdict'] == 'uncertain'


@pytest.mark.parametrize('damage', ['drop', 'paraphrase', 'duplicate', 'counterquote',
                                   'coverage_missing', 'coverage_duplicate', 'part_refuted_no_quote'])
def test_incomplete_or_invented_evidence_fails(prepared, damage):
    _, job = prepared
    response = reply(job)
    if damage == 'drop':
        response['parts'].pop()
    elif damage == 'paraphrase':
        response['parts'][1]['text'] = 'Usually calls str(value).'
    elif damage == 'duplicate':
        response['parts'].append(deepcopy(response['parts'][0]))
    elif damage == 'counterquote':
        response['parts'][1]['counterexamples'] = [{'source_id': 's1', 'quote': 'return "invented"'}]
    elif damage == 'coverage_missing':
        response['coverage'].pop()
    elif damage == 'coverage_duplicate':
        response['coverage'][1] = deepcopy(response['coverage'][0])
    else:
        response['parts'][1].update(verdict='refuted', citations=[])
    assert run(job, response)['status'] == 'failed'


def test_no_semantic_truth_is_inferred_from_consistent_assessments(prepared):
    _, job = prepared
    result = run(job, reply(job))
    # This authored answer hides the exception. Structural validation cannot find
    # an undeclared semantic error and MUST NOT claim independent correctness.
    assert result['result']['verdict'] == 'supported'
    assert result['aggregation']['semantic_decomposition'] == 'unverified'
    assert not result['semantic_verified']


def test_rehashed_result_cannot_bypass_reaggregation(prepared):
    _, job = prepared
    response = reply(job)
    response['parts'][1]['verdict'] = 'refuted'
    result = run(job, response)
    result['result']['verdict'] = 'supported'
    result['digest'] = content_digest({k: v for k, v in result.items() if k != 'digest'})
    with pytest.raises(ValueError, match='result_changed'):
        checked_proposal(result)


def test_global_doubt_is_not_promoted_and_refutation_requires_a_part(prepared):
    _, job = prepared
    response = reply(job)
    response['verdict'] = 'uncertain'
    assert run(job, response)['result']['verdict'] == 'uncertain'
    response['verdict'] = 'refuted'
    assert run(job, response)['status'] == 'failed'


def test_counterexample_outweighs_missing_context(prepared):
    _, job = prepared
    response = reply(job)
    response['parts'][1]['counterexamples'] = [{'source_id': 's1', 'quote': 'return "empty"'}]
    response['coverage'][0].update(status='missing', citations=[])
    assert run(job, response)['result']['verdict'] == 'refuted'


def test_requirements_are_frozen_and_sent_without_expected_answers(prepared):
    report, _ = prepared
    req = [{'id': 'connection', 'description': 'Show the entrypoint calling this function.'}]
    job = prepare_claim_review(report, 'scenarios.0', review_version=2, coverage_requirements=req)
    req[0]['description'] = 'mutated caller object'
    assert job['coverage_requirements'][0]['description'] != req[0]['description']
    assert 'expected_verdict' not in str(review_messages(job))
    with pytest.raises(ValueError):
        prepare_claim_review(report, 'scenarios.0', review_version=2, coverage_requirements=[])


def test_invalid_rehashed_requirements_fail_before_inference(prepared):
    _, job = prepared
    job['coverage_requirements'] = []
    job['digest'] = content_digest({k: v for k, v in job.items() if k != 'digest'})
    with pytest.raises(ValueError):
        run_claim_review(job, chat=lambda *a, **k: pytest.fail('Invalid job must not spend tokens'))


def test_decision_history_is_separate_current_and_forwarded(prepared):
    report, job = prepared
    response = reply(job)
    response['parts'][1]['verdict'] = 'refuted'
    proposal = run(job, response)
    before = deepcopy(report)
    rejected = record_review_decision(proposal, disposition='rejected', reviewer='source reviewer',
                                     reason='Correction needs further scrutiny.')
    accepted = record_review_decision(proposal, disposition='accepted', reviewer='source reviewer',
        reason='Checked both branches.', accepted_text=response['proposed_text'], ledger=rejected)
    assert len(rejected['events']) == 1 and len(accepted['events']) == 2
    attached = attach_proposals(audit_saved_description(report), [proposal], decisions=accepted)
    assert attached['review_decisions'] == accepted
    assert all(task['status'] == 'open' for task in attached['review_tasks'])
    packet = make_product_context(report, accepted_claim_ids=['purpose'], reviewer='fixture reviewer',
                                  review_proposals=[proposal], review_decisions=accepted)
    root = report['evidence']['root']
    analysis = frame_analysis({'root': root, 'summary': {'root': root}}, None, packet)
    architecture = build_architecture_decision(goal='Inspect', project_report=analysis)
    spec = build_technical_spec(architecture_decision=architecture)
    assert spec['product_context']['review_decisions'] == accepted
    assert spec['product_context']['claims'] == packet['claims'] and report == before
    assert not spec['product_context']['execution_authorized']
    from pathlib import Path
    (Path(root) / 'core.py').write_text('changed')
    with pytest.raises(ValueError, match='stale'):
        checked_product_context(packet, root)


def test_decision_requires_explicit_candidate_and_report_binding(prepared):
    report, job = prepared
    proposal = run(job, reply(job))
    with pytest.raises(ValueError, match='candidate_text_required'):
        record_review_decision(proposal, disposition='accepted', reviewer='reviewer', reason='Checked.')
    with pytest.raises(ValueError, match='attestation_required'):
        record_review_decision(proposal, disposition='rejected', reviewer='', reason='Checked.')
    ledger = record_review_decision(proposal, disposition='deferred', reviewer='reviewer', reason='Missing binding.')
    with pytest.raises(ValueError, match='invalid_claim_decisions'):
        checked_decisions(ledger, report_digest='different')
    ledger['events'][0]['previous_digest'] = 'fake'
    ledger['events'][0]['digest'] = content_digest({k: v for k, v in ledger['events'][0].items() if k != 'digest'})
    ledger['digest'] = content_digest({k: v for k, v in ledger.items() if k != 'digest'})
    with pytest.raises(ValueError, match='history'):
        checked_decisions(ledger)
