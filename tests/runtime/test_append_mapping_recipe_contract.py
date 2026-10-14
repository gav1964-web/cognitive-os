"""Installed recipe composition, single ownership and fresh admission checks."""
import json
from pathlib import Path

import pytest

from runtime import patch_synthesis_policy as policy
from runtime.competency_knowledge import invoke_knowledge
from runtime.recovery_pattern_clusters import implemented_clusters
from runtime._parts.config_doctor_catalogs import _load_catalogs
from tests.runtime.test_competency_knowledge import provider, _register, _write

ROOT = Path(__file__).resolve().parents[2]
LEGACY = json.loads((ROOT / 'tests/fixtures/append_mapping_policy_legacy.json').read_text(encoding='utf-8'))
KEY = 'extract_append_mapping_helper'


def test_installed_policy_preserves_complete_legacy_recipes():
    assert policy.load_patch_synthesis_policy() == LEGACY
    assert policy.append_mapping_helper_recipe() == LEGACY['recipes'][KEY]
    assert policy.development_helper_extraction_recipe(KEY) == LEGACY['recipes'][KEY]
    assert policy.framework_contract_recipe(KEY) == LEGACY['recipes'][KEY]
    assert LEGACY['recipes'][KEY]['target_cluster'] in implemented_clusters()
    records = invoke_knowledge('append_mapping', {'operation': 'patch_recipes'})['records']
    assert records == [{'id': KEY, 'recipe': LEGACY['recipes'][KEY]}]
    assert _load_catalogs(ROOT)['patch_synthesis_policy'] == LEGACY
    raw = policy.load_patch_synthesis_policy(policy.DEFAULT_PATH)
    assert KEY not in raw['recipes']
    assert raw['recipes'] == {k: v for k, v in LEGACY['recipes'].items() if k not in {KEY, 'extract_json_dumps_helper', 'extract_json_loads_helper', 'extract_splitlines_helper'}}


def test_supplied_document_does_not_import_installed_knowledge(tmp_path, monkeypatch):
    path = tmp_path / 'proposal.json'
    document = {'schema_version': 'patch_synthesis_policy.v1', 'recipes': {}}
    _write(path, document)
    def denied(*args, **kwargs):
        raise AssertionError('supplied document must remain independent')
    monkeypatch.setattr(policy, 'catalog_records', denied)
    assert policy.load_patch_synthesis_policy(path) == document


def test_unknown_recipe_owner_refreshes_without_cache_or_core_branch(provider):
    root, name, directory = provider
    _write(root / 'config/patch_synthesis_policy.json', {'schema_version': 'patch_synthesis_policy.v1', 'recipes': {}})
    _write(root / 'config/knowledge_providers.json', {'schema_version': 'knowledge_providers.v1',
        'providers': [{'capability': name, 'catalogs': ['patch_recipes'], 'profile_ids': []}]})
    record = {'id': 'new_recipe', 'recipe': {'enabled': True, 'maximum_items': 3}}
    _write(directory / 'knowledge/profile.json', record)
    _register(root, name)
    first = policy.load_installed_patch_synthesis_policy(root)
    assert first['recipes']['new_recipe']['maximum_items'] == 3
    first['recipes']['new_recipe']['maximum_items'] = 999
    assert policy.load_installed_patch_synthesis_policy(root)['recipes']['new_recipe']['maximum_items'] == 3
    record['recipe']['maximum_items'] = 2
    _write(directory / 'knowledge/profile.json', record)
    with pytest.raises(ValueError, match='identity_mismatch'):
        policy.load_installed_patch_synthesis_policy(root)
    _register(root, name)
    assert policy.load_installed_patch_synthesis_policy(root)['recipes']['new_recipe']['maximum_items'] == 2


@pytest.mark.parametrize('records,error', [
    ([{'id': 'local', 'recipe': {'enabled': True}}], 'duplicate_patch_recipe_owner'),
    ([{'id': 'other', 'recipe': {'enabled': True}}] * 2, 'duplicate_patch_recipe_owner'),
    ([{'id': '', 'recipe': {'enabled': True}}], 'invalid_patch_recipe_contribution'),
    ([{'id': 'other', 'recipe': {}}], 'invalid_patch_recipe_contribution'),
    ([{'id': 'other', 'recipe': []}], 'invalid_patch_recipe_contribution'),
])
def test_conflicting_or_malformed_contribution_is_rejected(tmp_path, monkeypatch, records, error):
    _write(tmp_path / 'config/patch_synthesis_policy.json', {
        'schema_version': 'patch_synthesis_policy.v1', 'recipes': {'local': {'enabled': True}}})
    monkeypatch.setattr(policy, 'catalog_records', lambda *a, **k: records)
    with pytest.raises(ValueError, match=error):
        policy.load_installed_patch_synthesis_policy(tmp_path)


def test_disabled_owner_recipe_remains_unavailable(monkeypatch):
    monkeypatch.setattr(policy, '_policy', lambda: {'recipes': {}})
    monkeypatch.setattr(policy, 'load_patch_synthesis_policy', lambda: {
        'recipes': {KEY: {**LEGACY['recipes'][KEY], 'enabled': False}}})
    assert policy.append_mapping_helper_recipe() == {}
    assert policy.development_helper_extraction_recipe(KEY) == {}
