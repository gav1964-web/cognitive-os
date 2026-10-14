"""Lossless envelope repair cannot approve semantics or rewrite historical failures."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from runtime.description_shape import normalize_description, report_draft
from runtime.project_description import describe_project, _validate_description, render_description
from runtime.project_description_review import draft_claims
from runtime.single_claim_review import prepare_claim_review
from runtime.description_offline_review import audit_saved_description
from runtime.product_context import make_product_context

ROOT = Path(__file__).resolve().parents[2]


def answer():
    claim = {'text': 'All inputs always succeed.', 'evidence_ids': ['s1']}
    return {'purpose': deepcopy(claim), 'scenarios': [deepcopy(claim)],
            'data_flow': deepcopy(claim), 'unknowns': [], 'confidence': 'high'}


@pytest.fixture
def project(tmp_path):
    (tmp_path / 'app.py').write_text('def run(value):\n    if value:\n        raise ValueError()\n', encoding='utf-8')
    return tmp_path


def chat(messages, *, config):
    payload = json.loads(messages[1]['content'])
    if 'draft' not in payload:
        return answer()
    corrected = deepcopy(payload['draft'])
    for claim in [corrected['purpose'], *corrected['scenarios'], *corrected['data_flow']]:
        claim['text'] = 'Raises an error for a truthy input.'
    corrected['data_flow'] = corrected['data_flow'][0]
    return {'description': corrected, 'corrections': ['Corrected universal success claim.'],
            'claim_reviews': [{'claim_id': c['id'], 'action': 'rephrased',
                               'reason': 'Conditional error in source.', 'evidence_ids': ['s1']}
                              for c in payload['draft_claims']]}


def test_saved_failure_remains_failed_but_lossless_copy_can_reach_review():
    fixture = json.loads((ROOT / 'tests/fixtures/project_description/singleton_flow_failure.json').read_text(encoding='utf-8'))
    raw = fixture['raw_response']
    original = deepcopy(raw)
    evidence = {'root': 'unused', 'sources': [
        {'id': ref, 'path': 'saved.py', 'sha256': '0'*64, 'excerpt': ''}
        for ref in fixture['evidence_ids']]}
    with pytest.raises(ValueError, match='invalid_data_flow'):
        report_draft({'raw_response': raw, 'evidence': evidence, 'status': 'failed'})
    normalized, receipt = normalize_description(raw, evidence)
    assert raw == original and normalized['data_flow'] == [raw['data_flow']]
    assert {k: v for k, v in normalized.items() if k != 'data_flow'} == {
        k: v for k, v in raw.items() if k != 'data_flow'}
    assert receipt['operations'] == [{'path': '/data_flow', 'operation': 'wrap_single_claim'}]
    assert receipt['semantic_verified'] is False
    assert receipt['raw_sha256'] != receipt['normalized_sha256']
    again, identity = normalize_description(normalized, evidence)
    assert again == normalized and identity['operations'] == []


def test_draft_and_review_preserve_raw_and_allow_semantic_correction(project):
    report = describe_project(project, chat=chat)
    assert report['status'] == 'described'
    assert report['raw_response'] == answer()
    assert isinstance(report['review_response']['description']['data_flow'], dict)
    assert report['review_rounds'][-1]['response'] == report['review_response']
    assert report['shape_normalization']['draft']['operations']
    assert report['shape_normalization']['review']['operations']
    assert report_draft(report)['purpose']['text'] == 'All inputs always succeed.'
    assert report['description']['purpose']['text'] == 'Raises an error for a truthy input.'
    assert report['verification']['semantic_review_required'] is True
    assert 'Raises an error' in render_description(report)


def test_downstream_uses_same_draft_ids_without_promoting_raw_claims(project):
    report = describe_project(project, chat=chat)
    job = prepare_claim_review(report, 'data_flow.0')
    assert job['original_claim']['text'] == 'All inputs always succeed.'
    audit = audit_saved_description(report)
    assert audit['draft_claims'][-1]['id'] == 'data_flow.0'
    packet = make_product_context(report, accepted_claim_ids=['purpose'], reviewer='fixture-author')
    assert packet['claims'][0]['text'] == 'Raises an error for a truthy input.'
    assert packet['execution_authorized'] is False
    with pytest.raises(ValueError, match='explicit_claim_review'):
        make_product_context(report, accepted_claim_ids=[], reviewer='fixture-author')


@pytest.mark.parametrize('field', ['raw', 'draft_receipt', 'review_receipt', 'description', 'review_raw', 'missing_draft'])
def test_downstream_rejects_tampered_provenance(project, field):
    report = describe_project(project, chat=chat)
    if field == 'raw':
        report['raw_response']['purpose']['text'] = 'Invented'
    elif field == 'draft_receipt':
        report['shape_normalization']['draft']['operations'] = []
    elif field == 'review_receipt':
        report['shape_normalization']['review']['semantic_verified'] = True
    elif field == 'description':
        report['description']['purpose']['text'] = 'Invented'
    elif field == 'review_raw':
        report['review_response']['description']['purpose']['text'] = 'Invented'
    else:
        del report['shape_normalization']['draft']
    with pytest.raises(ValueError, match='shape_receipt_mismatch'):
        make_product_context(report, accepted_claim_ids=['purpose'], reviewer='fixture-author')


@pytest.mark.parametrize('bad', [None, 'flow', [], [{'text': 'x', 'evidence_ids': ['missing']}],
    {'text': 'x', 'evidence_ids': 's1'}, {'text': 'x', 'evidence_ids': []},
    {'text': 'x', 'evidence_ids': ['missing']}, {'text': 'x', 'evidence_ids': ['s1'], 'extra': 1},
    {'text': ' ', 'evidence_ids': ['s1']}, {'text': 'x'*2001, 'evidence_ids': ['s1']}])
def test_bad_shape_or_citations_fail_before_review(project, bad):
    calls = []
    def invalid(messages, *, config):
        calls.append(messages)
        return {**answer(), 'data_flow': bad}
    report = describe_project(project, chat=invalid)
    assert len(calls) == 1 and report['status'] == 'failed' and report['description'] is None
    assert report['raw_response']['data_flow'] == bad


def test_normalized_draft_cannot_skip_or_fabricate_review(project):
    calls = []
    def incomplete(messages, *, config):
        calls.append(messages)
        if len(calls) == 1:
            return answer()
        return {'description': answer(), 'corrections': [], 'claim_reviews': []}
    report = describe_project(project, chat=incomplete)
    assert len(calls) == 2 and report['status'] == 'failed'
    assert report['reason'] == 'description_incomplete_claim_review'
    assert report['description'] is None
    with pytest.raises(ValueError, match='review_required'):
        make_product_context(report, accepted_claim_ids=['purpose'], reviewer='fixture-author')


def test_removed_normalized_claim_remains_visible_as_unverified(project):
    def removal(messages, *, config):
        response = chat(messages, config=config)
        if 'claim_reviews' in response:
            response['claim_reviews'][-1].update(action='removed', evidence_ids=[],
                                                reason='Insufficient evidence.')
        return response
    report = describe_project(project, chat=removal)
    assert report['unverified_removals'] == ['data_flow.0']
    assert 'All inputs always succeed.' in render_description(report)
    assert report['review_changes'][-1]['authority'] == 'unverified_draft_change'


def test_normalization_does_not_invent_scenario_ids_or_relax_other_fields(project):
    raw = answer()
    raw['scenarios'] = raw['scenarios'][0]
    calls = []
    def singleton(messages, *, config):
        calls.append(messages)
        return raw if len(calls) == 1 else chat(messages, config=config)
    report = describe_project(project, chat=singleton)
    assert [c['id'] for c in draft_claims(report_draft(report))] == ['purpose', 'scenarios.0', 'data_flow.0']
    with pytest.raises(ValueError, match='invalid_fields'):
        normalize_description({**raw, 'extra': 'unsupported'}, report['evidence'])
    with pytest.raises(ValueError, match='invalid_uncertainty'):
        normalize_description({**raw, 'unknowns': 'question'}, report['evidence'])
    with pytest.raises(ValueError, match='invalid_data_flow'):
        _validate_description(answer(), {'s1'})
