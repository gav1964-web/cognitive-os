"""Actual unknown plugins exercise dispatch, identity and KB freshness."""
import json
import uuid
from pathlib import Path

import pytest
import plugins

from runtime.competency_knowledge import catalog_records, decorate_profile, invoke_knowledge, providers
from runtime.plugin_loader import load_capability, load_capabilities
from runtime.registry import _registry_record


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


def _register(root, name):
    _write(root / 'registry/capabilities.json', {'capabilities': [_registry_record(load_capability(root, name))]})


@pytest.fixture
def provider(tmp_path, monkeypatch):
    name = 'test_knowledge_' + uuid.uuid4().hex[:12]
    directory = tmp_path / 'plugins' / name
    (directory / 'src').mkdir(parents=True)
    (directory / '__init__.py').write_text('', encoding='utf-8')
    (directory / 'src/__init__.py').write_text('', encoding='utf-8')
    (directory / 'src/main.py').write_text('''from pathlib import Path
import json

def run(payload):
    record = json.loads((Path(__file__).resolve().parents[1] / 'knowledge/profile.json').read_text())
    if payload['operation'] == 'decorate_profile':
        return {'status': 'ok', 'profile': record}
    return {'status': 'ok', 'records': [record]}
''', encoding='utf-8')
    _write(directory / 'knowledge/profile.json', {'id': 'new_domain', 'status': 'staged'})
    _write(directory / 'plugin.json', {'id': name, 'version': '0.1.0',
           'entrypoint': f'plugins.{name}.src.main:run', 'determinism_grade': 'B',
           'side_effects': {'filesystem': 'read_only', 'network': 'none', 'secrets': 'none'},
           'lifecycle_status': 'active'})
    _write(directory / 'schemas/input.json', {'type': 'object', 'additionalProperties': False,
           'required': ['operation'], 'properties': {'operation': {'type': 'string'}, 'profile': {'type': 'object'}}})
    _write(directory / 'schemas/output.json', {'type': 'object', 'additionalProperties': False,
           'required': ['status'], 'properties': {'status': {'const': 'ok'}, 'records': {'type': 'array'}, 'profile': {'type': 'object'}}})
    _write(tmp_path / 'config/knowledge_providers.json', {'schema_version': 'knowledge_providers.v1',
           'providers': [{'capability': name, 'catalogs': ['boundary_profiles'], 'profile_ids': ['new_domain']}]})
    monkeypatch.setattr(plugins, '__path__', [*plugins.__path__, str(tmp_path / 'plugins')])
    _register(tmp_path, name)
    return tmp_path, name, directory


def test_unknown_competency_works_without_domain_branches(provider):
    root, name, _ = provider
    assert load_capabilities(root)[name] == load_capability(root, name)
    assert catalog_records('boundary_profiles', root=root) == [{'id': 'new_domain', 'status': 'staged'}]
    assert decorate_profile({'id': 'new_domain'}, root=root)['status'] == 'staged'
    assert decorate_profile({'id': 'unowned'}, root=root) == {'id': 'unowned'}


def test_kb_change_rejects_old_hash_and_reads_new_value_after_registration(provider):
    root, name, directory = provider
    assert catalog_records('boundary_profiles', root=root)[0]['status'] == 'staged'
    _write(directory / 'knowledge/profile.json', {'id': 'new_domain', 'status': 'active'})
    with pytest.raises(ValueError, match='identity_mismatch'):
        catalog_records('boundary_profiles', root=root)
    _register(root, name)
    assert catalog_records('boundary_profiles', root=root)[0]['status'] == 'active'


def test_loaded_code_change_requires_restart_even_after_registration(provider):
    root, name, directory = provider
    catalog_records('boundary_profiles', root=root)
    code = directory / 'src/main.py'
    code.write_text(code.read_text() + '\n# changed code\n', encoding='utf-8')
    _register(root, name)
    with pytest.raises(ValueError, match='restart_required'):
        catalog_records('boundary_profiles', root=root)


@pytest.mark.parametrize('mutation', ['quarantined', 'missing', 'effects'])
def test_unauthorized_provider_does_not_run(provider, mutation):
    root, name, directory = provider
    if mutation == 'effects':
        path = directory / 'plugin.json'
        data = json.loads(path.read_text())
        data['side_effects']['filesystem'] = 'write_scoped'
        _write(path, data)
        _register(root, name)
    else:
        path = root / 'registry/capabilities.json'
        data = json.loads(path.read_text())
        if mutation == 'missing':
            data['capabilities'] = []
        else:
            data['capabilities'][0]['lifecycle_status'] = mutation
        _write(path, data)
    with pytest.raises(ValueError):
        catalog_records('boundary_profiles', root=root)


def test_conflicting_owners_and_foreign_profile_are_rejected(provider):
    root, name, directory = provider
    path = root / 'config/knowledge_providers.json'
    data = json.loads(path.read_text())
    data['providers'].append({**data['providers'][0], 'capability': 'another_provider'})
    _write(path, data)
    with pytest.raises(ValueError, match='ambiguous_knowledge_owner'):
        providers(root)
    data['providers'].pop()
    _write(path, data)
    _write(directory / 'knowledge/profile.json', {'id': 'someone_else', 'status': 'active'})
    _register(root, name)
    with pytest.raises(ValueError, match='owner_mismatch'):
        catalog_records('boundary_profiles', root=root)
    with pytest.raises(ValueError, match='invalid_decorated_profile'):
        decorate_profile({'id': 'new_domain'}, root=root)


def test_input_and_output_contracts_are_checked(provider):
    root, name, directory = provider
    with pytest.raises(Exception, match='input'):
        invoke_knowledge(name, {'unrecognized': True}, root=root)
    schema = directory / 'schemas/output.json'
    data = json.loads(schema.read_text())
    data['properties']['status']['const'] = 'different'
    _write(schema, data)
    _register(root, name)
    with pytest.raises(Exception, match='output'):
        catalog_records('boundary_profiles', root=root)


def test_generic_interpreter_has_no_pickle_import_or_branch():
    source = (Path(__file__).resolve().parents[2] / 'runtime/project_development_boundary_interpreter.py').read_text()
    assert 'pickle' not in source.lower()
