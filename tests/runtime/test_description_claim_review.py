from copy import deepcopy
import hashlib
import json

import pytest

from plugins.project_description.src.claim_evidence import literal_matches, review_context
from plugins.project_description.src.review_audit import audit_review
from runtime.description_offline_review import audit_saved_description
from runtime.project_description import describe_project, render_description
from runtime.project_description_review import draft_claims
from runtime.product_context import make_product_context
from runtime.upstream_role_handoff import frame_analysis
from runtime.architecture_decision_builder import build_architecture_decision
from runtime.technical_spec_builder import build_technical_spec


@pytest.fixture
def saved(tmp_path):
    text = 'def choose(value):\n    return "rapid" if value else "thorough"\n'
    (tmp_path / 'app.py').write_text(text)
    claim = {'text': "Chooses 'rapid' or 'thorough'.", 'evidence_ids': ['s1']}
    draft = {'purpose': dict(claim), 'scenarios': [dict(claim)], 'data_flow': [dict(claim)],
             'unknowns': [], 'confidence': 'medium'}
    reviews = [{'claim_id': c['id'], 'action': 'retained', 'reason': 'Read implementation.',
                'evidence_ids': ['s1']} for c in draft_claims(draft)]
    reviews[1].update(action='removed', evidence_ids=[], reason="Names 'rapid' and 'thorough' were not found.")
    source = {'id': 's1', 'path': 'app.py', 'sha256': hashlib.sha256((tmp_path / 'app.py').read_bytes()).hexdigest(),
              'excerpt': text, 'authority': 'source_excerpt', 'truncated': False}
    return {'status': 'described', 'evidence': {'root': str(tmp_path), 'sources': [source]},
            'raw_response': draft, 'description': deepcopy(draft), 'owner_notes': [],
            'claim_reviews': reviews}


def test_saved_removal_surfaces_matches_without_restoring_claim_or_calling_model(saved, monkeypatch):
    import runtime.local_inference as inference
    monkeypatch.setattr(inference, 'call_json_chat', lambda *a, **k: pytest.fail('No model allowed'))
    original = deepcopy(saved)
    result = audit_saved_description(saved)
    assert saved == original
    assert result['model_requests'] == 0
    assert result['review_audit']['status'] == 'needs_review'
    assert not result['review_audit']['semantic_verified']
    task = result['review_tasks'][0]
    assert task['claim_namespace'] == 'draft' and task['claim_id'] == 'scenarios.0'
    assert {m['term'] for m in task['finding']['matches']} == {'rapid', 'thorough'}
    assert task['id'] == audit_saved_description(saved)['review_tasks'][0]['id']
    assert not task['execution_authorized']


def test_literal_absence_is_checked_only_in_declared_excerpts(saved):
    claims = draft_claims(saved['raw_response'])
    reviews = saved['claim_reviews']
    reviews[1]['checks'] = [{'kind': 'literal_absent', 'value': 'rapid', 'evidence_ids': ['s1']}]
    audit = audit_review(saved['evidence'], claims, reviews)
    assert audit['findings'][0]['kind'] == 'contradicted_literal_absence'
    reviews[1]['checks'][0]['value'] = 'absent_value'
    audit = audit_review(saved['evidence'], claims, reviews)
    assert all(f['kind'] != 'contradicted_literal_absence' for f in audit['findings'])
    assert not audit['semantic_verified']


def test_hidden_text_does_not_falsely_contradict_a_check_of_visible_excerpt(saved):
    visible = deepcopy(saved['evidence'])
    visible['sources'][0]['excerpt'] = '[... omitted ...]'
    reviews = saved['claim_reviews']
    reviews[1]['checks'] = [{'kind': 'literal_absent', 'value': 'rapid', 'evidence_ids': ['s1']}]
    audit = audit_review(saved['evidence'], draft_claims(saved['raw_response']), reviews,
                         visible_evidence=visible)
    assert all(f['kind'] != 'contradicted_literal_absence' for f in audit['findings'])
    assert audit['findings'][0]['scope'] == 'full_saved_excerpts'
    visible['sources'][0]['sha256'] = '0' * 64
    with pytest.raises(ValueError, match='visible_source_mismatch'):
        audit_review(saved['evidence'], draft_claims(saved['raw_response']), reviews,
                     visible_evidence=visible)


@pytest.mark.parametrize('value', [None, {}, [{'kind': 'literal_absent', 'value': 'rapid', 'evidence_ids': ['fake']}],
                                  [{'kind': 'feature_absent', 'value': 'rapid', 'evidence_ids': ['s1']}],
                                  [{'kind': 'literal_absent', 'value': '', 'evidence_ids': ['s1']}]])
def test_malformed_mechanical_checks_fail_closed(saved, value):
    saved['claim_reviews'][1]['checks'] = value
    with pytest.raises(ValueError, match='literal_checks'):
        audit_saved_description(saved)


def test_word_boundaries_and_documentation_are_not_code_matches(saved):
    sources = saved['evidence']['sources']
    sources[0]['excerpt'] = 'return "rapidly"'
    assert not literal_matches('rapid', sources)
    sources[0].update(excerpt='return "rapid"', authority='documentation_claims')
    assert not literal_matches('rapid', sources)


def test_compact_context_is_bounded_and_preserves_matched_value(saved):
    evidence = saved['evidence']
    evidence['sources'][0]['excerpt'] = ('# padding\n' * 4000 + evidence['sources'][0]['excerpt'] + '# tail\n' * 4000)
    policy = {'max_context_characters': 8000, 'max_catalog_entries': 10, 'max_source_characters': 1600}
    result = review_context(evidence, draft_claims(saved['raw_response']), policy)
    assert result['context_characters'] <= 8000
    assert 'rapid' in result['evidence']['sources'][0]['excerpt']
    assert result['evidence']['sources'][0]['truncated']
    assert len(evidence['sources'][0]['excerpt']) > 20000


def test_stale_saved_sources_refuse_and_unfinished_review_keeps_draft_separate(saved):
    from pathlib import Path
    saved['status'] = 'failed'
    del saved['claim_reviews']
    result = audit_saved_description(saved)
    assert result['review_audit']['status'] == 'review_not_completed'
    assert len(result['review_tasks']) == 3
    assert 'description' not in result
    (Path(saved['evidence']['root']) / 'app.py').write_text('changed')
    with pytest.raises(ValueError, match='stale_sources'):
        audit_saved_description(saved)


def test_live_coordinator_adds_audit_tasks_and_roles_preserve_them(saved):
    from pathlib import Path
    project = Path(saved['evidence']['root'])
    def chat(messages, **kwargs):
        payload = json.loads(messages[1]['content'])
        if 'draft' not in payload:
            return saved['raw_response']
        assert payload['claim_packets'][0]['literal_matches']
        reviews = deepcopy(saved['claim_reviews'])
        reviews[1]['checks'] = [{'kind': 'literal_absent', 'value': 'rapid', 'evidence_ids': ['s1']}]
        return {'description': saved['description'], 'claim_reviews': reviews, 'corrections': []}
    report = describe_project(project, chat=chat)
    assert report['status'] == 'described'
    assert report['review_audit']['status'] == 'needs_review'
    assert 'Проверка обоснований review' in render_description(report)
    context = make_product_context(report, accepted_claim_ids=['purpose'], reviewer='test')
    analysis = frame_analysis({'root': str(project), 'summary': {'root': str(project)}}, None, context)
    architecture = build_architecture_decision(goal='Inspect', project_report=analysis)
    spec = build_technical_spec(architecture_decision=architecture)
    assert spec['product_context']['review_tasks'] == context['review_tasks']
    assert context['review_tasks'][0]['finding']['kind'] == 'contradicted_literal_absence'
    assert not spec['product_context']['execution_authorized']


def test_timeout_leaves_pending_review_tasks_without_publishing_draft(saved):
    from pathlib import Path
    from runtime.local_inference import LocalInferenceError
    calls = []
    def chat(messages, **kwargs):
        calls.append(messages)
        if len(calls) == 1:
            return saved['raw_response']
        raise LocalInferenceError('recorded timeout')
    result = describe_project(Path(saved['evidence']['root']), chat=chat)
    assert len(calls) == 2 and result['status'] == 'failed' and result['description'] is None
    assert len(result['review_tasks']) == 3
    assert result['review_audit']['status'] == 'review_not_completed'


def test_offline_cli_writes_audit_and_refuses_to_replace_source_report(saved, tmp_path, monkeypatch):
    from tools.audit_project_description import main
    original = tmp_path / 'report.json'
    output = tmp_path / 'audit.json'
    original.write_text(json.dumps(saved), encoding='utf-8')
    before = original.read_bytes()
    monkeypatch.setattr('sys.argv', ['audit', '--report', str(original), '--output', str(output)])
    assert main() == 0
    assert json.loads(output.read_text(encoding='utf-8'))['model_requests'] == 0
    assert original.read_bytes() == before
    monkeypatch.setattr('sys.argv', ['audit', '--report', str(original), '--output', str(original)])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2 and original.read_bytes() == before
