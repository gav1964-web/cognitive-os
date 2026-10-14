"""Research documents and installed KB have distinct registered operations."""
import hashlib
import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest

from runtime import exception_pickle_catalog_contract as client
from runtime.competency_knowledge import invoke_knowledge

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / client.RESEARCH_CATALOG_PATH
ABSENT = {'schema_version': 'exception_pickle_reconstruction_patterns.v1', 'status': 'absent'}


def _active():
    return json.loads(CATALOG.read_text(encoding='utf-8'))


def test_installed_and_missing_research_catalog_never_substitute_for_each_other(tmp_path):
    installed = client.read_installed_patterns()
    assert installed == _active() and installed['status'] == 'active'
    path = tmp_path / 'explicit-experiment.json'
    assert client.read_research_patterns(path) == ABSENT
    path.write_text(json.dumps(ABSENT), encoding='utf-8')
    assert client.read_research_patterns(path) == ABSENT
    assert client.read_installed_patterns() == installed


def test_explicit_document_validation_does_not_read_installed_catalog(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('supplied-document validation must not read installed knowledge')

    monkeypatch.setattr('plugins.exception_pickle.src.main.load_exception_pickle_patterns', forbidden)
    assert client.validate_research_patterns(ABSENT) == ABSENT
    assert client.validate_research_patterns(None) == ABSENT


def test_research_file_is_fresh_and_active_claim_does_not_modify_registration(tmp_path):
    tracked = [CATALOG, ROOT / 'registry/capabilities.json']
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked}
    path = tmp_path / 'experiment.json'
    document = _active()
    document['experimental_marker'] = {'trial': 'unpromoted'}
    path.write_text(json.dumps(document), encoding='utf-8')
    returned = client.read_research_patterns(path)
    assert returned == document
    returned['experimental_marker']['trial'] = 'mutated'
    assert client.read_research_patterns(path) == document
    path.write_text(json.dumps(ABSENT), encoding='utf-8')
    assert client.read_research_patterns(path) == ABSENT
    assert {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked} == before


def test_validation_does_not_share_mutable_document_state():
    document = _active()
    before = deepcopy(document)
    returned = client.validate_research_patterns(document)
    returned['safety']['source_apply_allowed'] = True
    assert document == before


@pytest.mark.parametrize('field', ['id', 'status', 'hypothesis_kind', 'reconstruction_method', 'state_strategy'])
def test_prior_operator_constraints_remain_required(field):
    document = _active()
    document['operator'][field] = 'unapproved'
    with pytest.raises(ValueError, match=f'invalid exception pickle operator.{field}'):
        client.validate_research_patterns(document)


@pytest.mark.parametrize('field', ['source_apply_allowed', 'automatic_runtime_mutation_allowed'])
def test_document_cannot_grant_source_mutation(field):
    document = _active()
    document['safety'][field] = True
    with pytest.raises(ValueError, match='unsafe exception pickle pattern policy'):
        client.validate_research_patterns(document)


@pytest.mark.parametrize('document,error', [
    ({}, 'schema mismatch'),
    ({**ABSENT, 'status': 'promoted'}, 'invalid exception pickle pattern lifecycle'),
])
def test_missing_and_malformed_documents_are_distinct(document, error):
    with pytest.raises(ValueError, match=error):
        client.validate_research_patterns(document)


def test_invalid_json_is_not_absence(tmp_path):
    path = tmp_path / 'invalid.json'
    path.write_text('{', encoding='utf-8')
    with pytest.raises(json.JSONDecodeError):
        client.read_research_patterns(path)


@pytest.mark.parametrize('payload', [
    {'operation': 'validate_patterns'},
    {'operation': 'validate_patterns', 'document': []},
    {'operation': 'validate_patterns', 'document': ABSENT, 'path': 'some-file.json'},
])
def test_validator_contract_accepts_data_not_paths(payload):
    with pytest.raises(Exception, match='exception_pickle.input'):
        invoke_knowledge('exception_pickle', payload)


def test_unregistered_validator_cannot_bypass_admission(tmp_path):
    plugin = tmp_path / 'plugins/exception_pickle'
    shutil.copytree(ROOT / 'plugins/exception_pickle', plugin)
    (tmp_path / 'registry').mkdir()
    shutil.copyfile(ROOT / 'registry/capabilities.json', tmp_path / 'registry/capabilities.json')
    kb = tmp_path / client.RESEARCH_CATALOG_PATH
    kb.write_text(json.dumps(ABSENT), encoding='utf-8')
    with pytest.raises(ValueError, match='knowledge_provider_identity_mismatch'):
        client.validate_research_patterns(ABSENT, competency_root=tmp_path)


def test_wrong_operation_response_is_not_a_catalog(monkeypatch):
    monkeypatch.setattr(client, 'invoke_knowledge', lambda *args, **kwargs: {'status': 'ok', 'samples': []})
    with pytest.raises(ValueError, match='invalid_exception_pickle_catalog_response'):
        client.read_installed_patterns()
    with pytest.raises(ValueError, match='invalid_exception_pickle_catalog_response'):
        client.validate_research_patterns(None)
