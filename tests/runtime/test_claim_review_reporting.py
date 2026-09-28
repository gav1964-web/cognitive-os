"""Saved failures and model/contract disagreement stay visible to a reader."""
from copy import deepcopy
import hashlib
import json

import pytest

from runtime.single_claim_review import prepare_claim_review, run_claim_review
from runtime.claim_review_decisions import record_review_decision
from runtime.claim_review_reporting import inspect_review, render_review
from runtime.narrow_type_evidence_binding import content_digest


@pytest.fixture
def sample(tmp_path):
    source = 'def status():\n    return "ready"\n'
    path = tmp_path / 'core.py'
    path.write_bytes(source.encode())
    claim = {'text': 'Возвращает ready.', 'evidence_ids': ['s1']}
    draft = {'purpose': claim, 'scenarios': [claim], 'data_flow': [claim], 'unknowns': [], 'confidence': 'medium'}
    report = {'status': 'described', 'raw_response': draft, 'description': deepcopy(draft),
              'evidence': {'root': str(tmp_path), 'sources': [{'id': 's1', 'path': 'core.py',
                  'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'excerpt': source}]}}
    job = prepare_claim_review(report, 'scenarios.0', review_version=2)
    quote = [{'source_id': 's1', 'quote': 'return "ready"'}]
    response = {'verdict': 'supported', 'reason': 'Виден return.', 'citations': quote, 'proposed_text': None,
                'parts': [{'text': claim['text'], 'verdict': 'supported', 'reason': 'Виден return.',
                           'citations': quote, 'counterexamples': []}],
                'coverage': [{'id': row['id'], 'status': 'shown', 'reason': 'Прямая функция.',
                              'citations': quote} for row in job['coverage_requirements']]}
    return job, response, path


def test_missing_context_explains_overridden_verdict_without_rewriting_model(sample):
    job, response, _ = sample
    response['coverage'][0].update(status='missing', citations=[])
    receipt = run_claim_review(job, chat=lambda *a, **k: response)
    inspection = inspect_review(receipt)
    assert inspection['model_verdict'] == 'supported' and inspection['effective_verdict'] == 'uncertain'
    text = render_review(inspection)
    assert 'Мнение модели: **подтверждено**' in text
    assert 'Контракт ответа: соблюдён.' in text
    assert 'Итог по оценкам модели: **неопределённо**' in text
    assert 'Недостающий контекст (scope)' in text
    assert not inspection['semantic_verified'] and not inspection['usage_known']


def test_malformed_model_answer_is_readable_but_has_no_effective_verdict(sample):
    job, response, _ = sample
    response['verdict'] = ['wrong type']
    receipt = run_claim_review(job, chat=lambda *a, **k: response)
    assert receipt['status'] == 'failed'
    inspection = inspect_review(receipt)
    assert inspection['effective_verdict'] is None and inspection['contract_status'] == 'failed'
    assert 'предложение не прошло проверку' in render_review(inspection)


def test_latest_reviewer_decision_and_stale_sources_are_explicit(sample):
    job, response, path = sample
    receipt = run_claim_review(job, chat=lambda *a, **k: response)
    first = record_review_decision(receipt, disposition='deferred', reviewer='reviewer', reason='Проверить источник.')
    latest = record_review_decision(receipt, disposition='accepted', reviewer='reviewer', reason='Источник проверен.',
                                    accepted_text=job['claim']['text'], ledger=first)
    inspection = inspect_review(receipt, decisions=latest)
    assert inspection['reviewer_decision']['disposition'] == 'accepted'
    assert 'Решение рецензента reviewer: принято' in render_review(inspection)
    path.write_text('changed')
    inspection = inspect_review(receipt)
    assert inspection['source_status'] != 'current' and inspection['effective_verdict'] is None
    assert 'Текущие источники не подтверждены' in render_review(inspection)


def test_tampered_receipt_is_rejected(sample):
    job, response, _ = sample
    receipt = run_claim_review(job, chat=lambda *a, **k: response)
    receipt['result']['verdict'] = 'refuted'
    with pytest.raises(ValueError, match='invalid_claim_review_receipt'):
        inspect_review(receipt)
    receipt['digest'] = content_digest({k: v for k, v in receipt.items() if k != 'digest'})
    inspection = inspect_review(receipt)
    assert inspection['contract_status'] == 'failed' and inspection['effective_verdict'] is None


def test_inspect_cli_preserves_receipt_and_refuses_markdown_overwrite(sample, tmp_path, monkeypatch):
    from tools.review_description_claim import main
    job, response, _ = sample
    receipt = run_claim_review(job, chat=lambda *a, **k: response)
    original, output, markdown = tmp_path / 'receipt.json', tmp_path / 'inspection.json', tmp_path / 'inspection.md'
    original.write_text(json.dumps(receipt), encoding='utf-8')
    before = original.read_bytes()
    monkeypatch.setattr('sys.argv', ['review', 'inspect', '--receipt', str(original), '--output', str(output),
                                    '--markdown', str(markdown)])
    assert main() == 0 and original.read_bytes() == before
    assert 'Мнение модели' in markdown.read_text(encoding='utf-8')
    monkeypatch.setattr('sys.argv', ['review', 'inspect', '--receipt', str(original), '--output', str(output),
                                    '--markdown', str(original)])
    with pytest.raises(SystemExit):
        main()
    assert original.read_bytes() == before
