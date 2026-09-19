import hashlib
import json
from pathlib import Path

import pytest

from plugins.project_description.src.main import run
from plugins.project_description.src.source_lookup import read_requests
from runtime.project_description import describe_project
from runtime.project_description_review import draft_claims

ROOT = Path(__file__).resolve().parents[2]


def answer():
    claim = {'text': 'Routes work to a local handler.', 'evidence_ids': ['s1']}
    return {'purpose': claim, 'scenarios': [dict(claim)], 'data_flow': [dict(claim)],
            'unknowns': [], 'confidence': 'medium'}


def reviewed(draft):
    return {'description': draft, 'corrections': [], 'claim_reviews': [
        {'claim_id': row['id'], 'action': 'retained', 'reason': 'Read implementation.',
         'evidence_ids': row['evidence_ids']} for row in draft_claims(draft)]}


@pytest.fixture
def project(tmp_path):
    (tmp_path / 'app').mkdir()
    (tmp_path / 'app/server.py').write_text('from .worker import process\ndef main(): return process()\n')
    (tmp_path / 'app/worker.py').write_text('def process():\n    return "LOOKUP_CANARY"\n')
    return tmp_path


def test_import_chain_prioritizes_application_and_marks_auxiliary(project):
    (project / 'scratch').mkdir()
    (project / 'scratch/pack.py').write_text('def backup(): return 1\n')
    evidence = run({'project_root': str(project)})['evidence']
    rows = evidence['sources']
    assert [r['path'] for r in rows[:2]] == ['app/server.py', 'app/worker.py']
    assert rows[0]['local_dependencies'] == ['app/worker.py']
    assert rows[-1]['auxiliary']


def test_reviewer_gets_one_hash_bound_lookup_round(project):
    calls = []
    def chat(messages, **kwargs):
        calls.append(messages)
        if len(calls) == 1:
            return answer()
        if len(calls) == 2:
            return {'requests': [{'path': 'app/worker.py', 'symbol': 'process'}]}
        payload = json.loads(messages[1]['content'])
        assert not payload['lookup_available']
        assert payload['required_response'] == 'final_review'
        assert payload['lookup_history'][0]['request'] == {'path': 'app/worker.py', 'symbol': 'process'}
        assert payload['lookup_history'][0]['source_id'] == 'x1'
        extra = payload['evidence']['sources'][-1]
        assert extra['id'] == 'x1' and 'LOOKUP_CANARY' in extra['excerpt']
        result = answer()
        result['purpose']['evidence_ids'] = ['x1']
        return reviewed(result)
    result = describe_project(project, chat=chat)
    assert result['status'] == 'described' and len(calls) == 3
    assert len(result['review_rounds']) == 2
    first = json.loads(result['review_rounds'][0]['request'][1]['content'])
    assert all(row['id'] != 'x1' for row in first['evidence']['sources'])
    assert first['lookup_history'] == []


@pytest.mark.parametrize('kind', ['unknown_path', 'repeat', 'changed', 'missing_claim', 'invalid_path_type'])
def test_lookup_and_claim_review_fail_closed(project, kind):
    calls = []
    def chat(messages, **kwargs):
        calls.append(messages)
        if len(calls) == 1:
            return answer()
        if kind == 'missing_claim':
            result = reviewed(answer())
            result['claim_reviews'].pop()
            return result
        if kind == 'changed':
            (project / 'app/worker.py').write_text('def process(): return 2\n')
        if kind == 'invalid_path_type':
            return {'requests': [{'path': ['not-a-string']}]}
        return {'requests': [{'path': '../outside.py' if kind == 'unknown_path' else 'app/worker.py',
                              'symbol': 'process'}]}
    result = describe_project(project, chat=chat)
    assert result['status'] == 'failed' and result['description'] is None
    assert len(calls) <= 3


@pytest.mark.parametrize('name', ['../outside.py', '.env', 'config.json', 'data/private.py'])
def test_direct_lookup_rejects_private_and_outside_paths(project, name):
    policy = json.loads((ROOT / 'plugins/project_description/knowledge/description_policy.json').read_text())['collection']
    with pytest.raises((ValueError, OSError)):
        read_requests(project, [{'path': name, 'sha256': '0' * 64}], policy)


def test_lookup_redacts_literals_and_checks_hash(project):
    file = project / 'app/worker.py'
    file.write_text('def process():\n    api_key = "HIDDEN_LITERAL"\n    return api_key\n')
    request = {'path': 'app/worker.py', 'symbol': 'process', 'sha256': hashlib.sha256(file.read_bytes()).hexdigest()}
    result = run({'project_root': str(project), 'action': 'read', 'requests': [request]})
    assert 'HIDDEN_LITERAL' not in json.dumps(result)
    request['sha256'] = '0' * 64
    with pytest.raises(ValueError, match='source_changed'):
        run({'project_root': str(project), 'action': 'read', 'requests': [request]})


def test_removed_claim_without_evidence_is_flagged_not_a_published_fact(project):
    def chat(messages, **kwargs):
        if 'draft' not in json.loads(messages[1]['content']):
            return answer()
        response = reviewed(answer())
        response['claim_reviews'][1].update(action='removed', evidence_ids=[],
                                            reason='Not enough evidence; requires human review.')
        return response
    result = describe_project(project, chat=chat)
    assert result['status'] == 'described'
    assert result['unverified_removals'] == ['scenarios.0']
    assert result['verification']['semantic_review_required']
    assert result['review_changes'][0]['draft_text'] == answer()['scenarios'][0]['text']


def test_rephrased_claim_remains_visible_to_downstream_review(project):
    from runtime.product_context import make_product_context
    def chat(messages, **kwargs):
        if 'draft' not in json.loads(messages[1]['content']):
            return answer()
        response = reviewed(answer())
        response['description']['scenarios'][0]['text'] = 'Processes work.'
        response['claim_reviews'][1].update(action='rephrased', reason='Details not shown.')
        return response
    result = describe_project(project, chat=chat)
    packet = make_product_context(result, accepted_claim_ids=['purpose'], reviewer='test')
    gap = packet['review_gaps'][0]
    assert gap['draft_text'] == answer()['scenarios'][0]['text']
    assert gap['action'] == 'rephrased' and gap['authority'] == 'unverified_draft_change'
    assert gap['draft_text'] not in [row['text'] for row in packet['claims'] if row['id'] != 'purpose']


def test_retained_claim_without_evidence_is_rejected(project):
    def chat(messages, **kwargs):
        if 'draft' not in json.loads(messages[1]['content']):
            return answer()
        response = reviewed(answer())
        response['claim_reviews'][0]['evidence_ids'] = []
        return response
    result = describe_project(project, chat=chat)
    assert result['status'] == 'failed'
    assert result['reason'] == 'description_invalid_claim_review'
