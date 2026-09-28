"""Pure preparation preserves bytes; governance rejects before preparation/write."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from runtime import exception_pickle_promotion_contract as client
from runtime import exception_pickle_promotion_transaction as transaction
from runtime.competency_knowledge import invoke_knowledge
from tests.runtime.test_exception_pickle_promotion_transaction import _fixture

ROOT = Path(__file__).resolve().parents[2]
FROZEN = json.loads((ROOT / 'tests/fixtures/exception_pickle_promotion_legacy.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('case', FROZEN['cases'])
def test_preparation_preserves_legacy_bytes_and_does_not_activate(case):
    tracked = [ROOT / transaction.CATALOG_PATH, ROOT / 'registry/capabilities.json']
    before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked]
    request = deepcopy(case['request'])
    result = invoke_knowledge('exception_pickle', {'operation': 'prepare_promotion', **request})
    assert result['status'] == 'prepared'
    encode = lambda data: (json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode('utf-8')
    assert encode(result['catalog']) == encode(case['catalog'])
    assert client.prepare_promotion_catalog(**request) == case['catalog']
    result['catalog']['promotion_evidence']['supervised_reports'].append({'mutated': True})
    assert request == case['request']
    assert [hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked] == before


def _call(root, paths, **overrides):
    readiness, evaluator, holdout, _ = paths
    return transaction.promote_exception_pickle_reconstruction(
        root=root, readiness_path=readiness, evaluator_review_path=evaluator, holdout_path=holdout,
        **{'explicit_approval': True, 'regression_passed': True, 'config_doctor_passed': True, **overrides})


@pytest.mark.parametrize('document,field,value,failed_check', [
    (None, 'explicit_approval', False, 'explicit_approval'),
    (None, 'regression_passed', False, 'regression_tests'),
    (None, 'config_doctor_passed', False, 'config_doctor'),
    (0, 'status', 'ineligible', 'readiness_status'),
    (0, 'promotion_review_allowed', False, 'readiness_allows_review'),
    (0, 'autonomous_activation_allowed', False, 'readiness_has_autonomous_activation_gate'),
    (0, 'kb_promotion_allowed', True, 'readiness_blocks_direct_kb_promotion'),
    (1, 'status', 'failed', 'independent_evaluator_passed'),
    (2, 'status', 'blocked', 'holdout_transaction_ready'),
])
def test_every_existing_gate_blocks_before_plugin_and_preserves_file(tmp_path, monkeypatch, document, field, value, failed_check):
    paths = _fixture(tmp_path)
    paths[3].parent.mkdir(parents=True)
    paths[3].write_bytes(b'existing catalog must survive')
    if document is not None:
        payload = json.loads(paths[document].read_text(encoding='utf-8'))
        payload[field] = value
        paths[document].write_text(json.dumps(payload), encoding='utf-8')
    monkeypatch.setattr(client, 'invoke_knowledge', lambda *a, **k: pytest.fail('blocked transaction called plugin'))
    report = _call(tmp_path, paths, **({field:value} if document is None else {}))
    assert report['status'] == 'blocked' and report['failed_checks'] == [failed_check]
    assert report['kb_promotion'] is False
    assert paths[3].read_bytes() == b'existing catalog must survive'


def test_admitted_transaction_writes_prepared_bytes_without_updating_registry(tmp_path, monkeypatch):
    paths = _fixture(tmp_path)
    (tmp_path / 'registry').mkdir()
    registry = tmp_path / 'registry/capabilities.json'
    registry.write_bytes(b'registry is owned by registration workflow')
    seen = []
    original = client.invoke_knowledge

    def capture(*args, **kwargs):
        result = original(*args, **kwargs)
        seen.append(result)
        return result

    monkeypatch.setattr(client, 'invoke_knowledge', capture)
    report = _call(tmp_path, paths)
    assert report['status'] == 'promoted' and len(seen) == 1
    expected = (json.dumps(seen[0]['catalog'], ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode('utf-8')
    assert paths[3].read_bytes() == expected
    assert report['after_digest'] == hashlib.sha256(expected).hexdigest()
    assert registry.read_bytes() == b'registry is owned by registration workflow'


@pytest.mark.parametrize('failure', ['admission', 'unsafe_document', 'absent_document'])
def test_preparation_failure_never_reaches_write(tmp_path, monkeypatch, failure):
    paths = _fixture(tmp_path)
    paths[3].parent.mkdir(parents=True)
    paths[3].write_bytes(b'previous bytes')
    if failure == 'admission':
        def denied(*args, **kwargs):
            raise ValueError('knowledge_provider_identity_mismatch')
        monkeypatch.setattr(client, 'invoke_knowledge', denied)
        error = 'knowledge_provider_identity_mismatch'
    else:
        catalog = deepcopy(FROZEN['cases'][0]['catalog'])
        if failure == 'unsafe_document':
            catalog['safety']['source_apply_allowed'] = True
            error = 'unsafe exception pickle pattern policy'
        else:
            catalog = None
            error = 'exception_pickle.output'
        monkeypatch.setattr('plugins.exception_pickle.src.main.prepare_promotion_catalog', lambda **kwargs: catalog)
    with pytest.raises(Exception, match=error):
        _call(tmp_path, paths)
    assert paths[3].read_bytes() == b'previous bytes'


def test_atomic_replace_error_keeps_previous_catalog(tmp_path, monkeypatch):
    paths = _fixture(tmp_path)
    paths[3].parent.mkdir(parents=True)
    paths[3].write_bytes(b'previous bytes')
    def denied(*args, **kwargs):
        raise OSError('replace denied')
    monkeypatch.setattr(transaction.os, 'replace', denied)
    with pytest.raises(OSError, match='replace denied'):
        _call(tmp_path, paths)
    assert paths[3].read_bytes() == b'previous bytes'
    assert list(paths[3].parent.iterdir()) == [paths[3]]


@pytest.mark.parametrize('extra', [{'explicit_approval':True}, {'catalog_path':'live.json'}])
def test_preparation_contract_does_not_accept_write_authority(extra):
    with pytest.raises(Exception, match='exception_pickle.input'):
        invoke_knowledge('exception_pickle', {'operation':'prepare_promotion', **FROZEN['cases'][0]['request'], **extra})
