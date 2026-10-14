from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from runtime.single_claim_review import prepare_claim_review as prepare_current_review, run_claim_review, review_messages
from runtime.claim_review_proposals import attach_proposals, checked_proposal
from runtime.description_offline_review import audit_saved_description
from runtime.product_context import make_product_context
from runtime.upstream_role_handoff import frame_analysis
from runtime.architecture_decision_builder import build_architecture_decision
from runtime.technical_spec_builder import build_technical_spec
from runtime.narrow_type_evidence_binding import content_digest
from runtime.local_inference import LocalInferenceError


def prepare_claim_review(*args, **kwargs):
    # Frozen v1 jobs/receipts retain their original contract.
    return prepare_current_review(*args, review_version=1, **kwargs)


@pytest.fixture
def saved(tmp_path):
    text = 'def choose(value):\n    return "rapid" if value else "thorough"\n'
    file = tmp_path / 'app.py'
    file.write_text(text)
    claim = {'text': "Chooses 'rapid' only when value is true.", 'evidence_ids': ['s1']}
    draft = {'purpose': dict(claim), 'scenarios': [dict(claim)], 'data_flow': [dict(claim)],
             'unknowns': [], 'confidence': 'medium'}
    return {'status': 'described', 'evidence': {'root': str(tmp_path), 'sources': [
        {'id': 's1', 'path': 'app.py', 'sha256': hashlib.sha256(file.read_bytes()).hexdigest(),
         'excerpt': text, 'authority': 'source_excerpt', 'truncated': False}]},
        'raw_response': draft, 'description': deepcopy(draft), 'owner_notes': []}


def response():
    return {'verdict': 'supported', 'reason': 'The branch is conditional.',
            'citations': [{'source_id': 's1', 'quote': 'return "rapid" if value else "thorough"'}],
            'proposed_text': None}


def test_prepare_is_bounded_immutable_and_can_read_hash_bound_symbol(saved):
    original = deepcopy(saved)
    job = prepare_claim_review(saved, 'scenarios.0')
    assert job['source_report_digest'] == content_digest(saved)
    assert sum(len(m['content']) for m in review_messages(job)) < 15000
    looked = prepare_claim_review(saved, 'scenarios.0', requests=[{'path': 'app.py', 'symbol': 'choose'}])
    assert 'def choose' in looked['evidence']['sources'][0]['excerpt']
    assert looked['evidence']['sources'][0]['id'] == 'x1'
    assert saved == original
    with pytest.raises(ValueError, match='unknown_lookup'):
        prepare_claim_review(saved, 'scenarios.0', requests=[{'path': '../private.py'}])


@pytest.mark.parametrize('kind', ['quote', 'source_id', 'missing', 'verdict', 'extra'])
def test_bad_result_is_not_a_reviewed_proposal(saved, kind):
    reply = response()
    if kind == 'quote':
        reply['citations'][0]['quote'] = 'return "rapid" unconditionally'
    elif kind == 'source_id':
        reply['citations'][0]['source_id'] = 'invented'
    elif kind == 'missing':
        reply['citations'] = []
    elif kind == 'verdict':
        reply['verdict'] = 'certified'
    else:
        reply['execute'] = True
    result = run_claim_review(prepare_claim_review(saved, 'scenarios.0'), chat=lambda *a, **k: reply)
    assert result['status'] == 'failed'
    assert not result['semantic_verified'] and not result['execution_authorized']
    with pytest.raises(ValueError):
        checked_proposal(result)


def test_timeout_has_no_fallback_or_retry(saved):
    calls = []
    def chat(messages, *, config):
        calls.append(messages)
        assert config.fallbacks == ()
        raise LocalInferenceError('recorded timeout')
    result = run_claim_review(prepare_claim_review(saved, 'scenarios.0'), chat=chat)
    assert len(calls) == 1 and result['status'] == 'failed'


def test_sources_are_checked_before_and_after_request(saved):
    job = prepare_claim_review(saved, 'scenarios.0')
    source = Path(saved['evidence']['root']) / 'app.py'
    def chat(*args, **kwargs):
        source.write_text('changed')
        return response()
    result = run_claim_review(job, chat=chat)
    assert result['status'] == 'failed' and result['reason'] == 'claim_review_stale_sources'
    with pytest.raises(ValueError, match='stale_sources'):
        run_claim_review(job, chat=lambda *a, **k: pytest.fail('No call with stale input'))


def test_proposal_is_report_bound_and_never_closes_tasks_or_rewrites_facts(saved):
    original = deepcopy(saved)
    job = prepare_claim_review(saved, 'scenarios.0')
    proposal = run_claim_review(job, chat=lambda *a, **k: response())
    assert proposal['status'] == 'reviewed'
    audit = audit_saved_description(saved)
    attached = attach_proposals(audit, [proposal])
    assert all(task['status'] == 'open' for task in attached['review_tasks'])
    assert attached['review_tasks'][1]['proposal_digests'] == [proposal['digest']]
    assert 'review_proposals' not in audit
    context = make_product_context(saved, accepted_claim_ids=['purpose'], reviewer='test', review_proposals=[proposal])
    root = saved['evidence']['root']
    analysis = frame_analysis({'root': root, 'summary': {'root': root}}, None, context)
    architecture = build_architecture_decision(goal='Inspect', project_report=analysis)
    spec = build_technical_spec(architecture_decision=architecture)
    assert spec['product_context']['review_proposals'] == context['review_proposals']
    assert saved == original
    assert not spec['product_context']['execution_authorized']
    other = deepcopy(saved)
    other['owner_notes'] = [{'text': 'different report'}]
    with pytest.raises(ValueError, match='wrong_report'):
        checked_proposal(proposal, report=other)
    with pytest.raises(ValueError, match='duplicate'):
        attach_proposals(audit, [proposal, proposal])


def test_rehashed_bad_quote_is_revalidated(saved):
    proposal = run_claim_review(prepare_claim_review(saved, 'scenarios.0'), chat=lambda *a, **k: response())
    proposal['result']['citations'][0]['quote'] = 'a fabricated statement'
    proposal['raw_response']['citations'][0]['quote'] = 'a fabricated statement'
    proposal['digest'] = content_digest({k: v for k, v in proposal.items() if k != 'digest'})
    with pytest.raises(ValueError, match='quote_not_in_visible_source'):
        checked_proposal(proposal)


def test_cli_prepare_does_not_execute_and_preserves_input(saved, tmp_path, monkeypatch):
    from tools.review_description_claim import main
    original, output = tmp_path / 'report.json', tmp_path / 'job.json'
    original.write_text(json.dumps(saved), encoding='utf-8')
    before = original.read_bytes()
    monkeypatch.setattr('sys.argv', ['review', 'prepare', '--report', str(original), '--claim-id',
                                   'scenarios.0', '--output', str(output)])
    assert main() == 0 and original.read_bytes() == before
    assert json.loads(output.read_text(encoding='utf-8'))['schema_version'] == 'single_claim_review_job.v4'
