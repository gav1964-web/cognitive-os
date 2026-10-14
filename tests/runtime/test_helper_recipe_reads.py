"""Bounded catalog reads retain admission at each selection/verification boundary."""
import json
from pathlib import Path

import pytest

from runtime import patch_synthesis_policy as policy
from runtime import programmer_patch_synthesizer_recovery as recovery
from runtime.recovery_patch_verification import verify_recovery_patch_package
from tests.runtime.test_competency_knowledge import provider, _register, _write

ROOT = Path(__file__).resolve().parents[2]
LEGACY = json.loads((ROOT / 'tests/fixtures/append_mapping_policy_legacy.json').read_text(encoding='utf-8'))
KEYS = ('extract_append_mapping_helper', 'extract_json_dumps_helper',
        'extract_json_loads_helper', 'extract_splitlines_helper')


@pytest.mark.parametrize('key', KEYS)
def test_one_catalog_read_per_selection_and_separate_verification(tmp_path, monkeypatch, key):
    calls = []
    original = policy.catalog_records

    def counted(*args, **kwargs):
        calls.append(args[0])
        return original(*args, **kwargs)

    monkeypatch.setattr(policy, 'catalog_records', counted)
    recipe = policy.development_helper_extraction_recipe(key)
    assert recipe == LEGACY['recipes'][key]
    assert calls == ['patch_recipes']
    package = recovery.synthesize_recovery_patch_package(
        execution_dir=tmp_path / 'execution', project_dir=tmp_path,
        recovery_route={'research_hypothesis': {
            'proposed_target': 'absent.py:' + recipe['required_candidate_symbol']}})
    assert package['reason'] == 'recovery_route_not_admitted'
    assert calls == ['patch_recipes'] * 2
    verification = verify_recovery_patch_package(
        project_dir=tmp_path, verification_dir=tmp_path / 'verification',
        patch_package={'status': 'prepared', 'patches': [{'kind': key, 'file': 'absent.py'}]})
    assert verification['reason'] == 'verification_source_missing'
    assert calls == ['patch_recipes'] * 3
    assert not (tmp_path / 'execution').exists()


def test_order_disabled_missing_and_unknown_recipes(monkeypatch):
    recipes = {key: dict(LEGACY['recipes'][key]) for key in reversed(KEYS)}
    recipes[KEYS[1]]['enabled'] = False
    del recipes[KEYS[2]]
    recipes['unknown'] = {'operation_kind': 'unknown'}
    monkeypatch.setattr(policy, 'load_patch_synthesis_policy', lambda: {'recipes': recipes})
    assert policy.helper_extraction_recipes() == (recipes[KEYS[0]], {}, {}, recipes[KEYS[3]])
    assert policy.development_helper_extraction_recipe(KEYS[1]) == {}
    assert policy.development_helper_extraction_recipe('unknown') == {}


@pytest.fixture
def recipe_provider(provider, monkeypatch):
    root, name, directory = provider
    _write(root / 'config/patch_synthesis_policy.json',
           {'schema_version': 'patch_synthesis_policy.v1', 'recipes': {}})
    _write(root / 'config/knowledge_providers.json', {'schema_version': 'knowledge_providers.v1',
           'providers': [{'capability': name, 'catalogs': ['patch_recipes'], 'profile_ids': []}]})
    _write(directory / 'knowledge/profile.json', {'id': KEYS[0], 'recipe': LEGACY['recipes'][KEYS[0]]})
    _register(root, name)
    original = policy.load_installed_patch_synthesis_policy
    monkeypatch.setattr(policy, 'load_installed_patch_synthesis_policy', lambda: original(root))
    return root, name, directory


def test_next_read_sees_registered_kb_update_and_ignores_result_mutation(recipe_provider):
    root, name, directory = recipe_provider
    first = policy.helper_extraction_recipes()
    first[0]['maximum_mapping_fields'] = 999
    assert policy.helper_extraction_recipes()[0]['maximum_mapping_fields'] != 999
    record = {'id': KEYS[0], 'recipe': {**LEGACY['recipes'][KEYS[0]], 'maximum_mapping_fields': 2}}
    _write(directory / 'knowledge/profile.json', record)
    with pytest.raises(ValueError, match='identity_mismatch'):
        policy.helper_extraction_recipes()
    _register(root, name)
    assert policy.helper_extraction_recipes()[0]['maximum_mapping_fields'] == 2


@pytest.mark.parametrize('boundary', ['candidate', 'verification'])
@pytest.mark.parametrize('mutation', ['kb', 'quarantine', 'missing'])
def test_changed_admission_is_rejected_at_next_boundary(recipe_provider, monkeypatch, boundary, mutation):
    root, name, directory = recipe_provider
    policy.helper_extraction_recipes()

    def change_admission():
        if mutation == 'kb':
            record = {'id': KEYS[0], 'recipe': {**LEGACY['recipes'][KEYS[0]], 'enabled': False}}
            _write(directory / 'knowledge/profile.json', record)
        else:
            path = root / 'registry/capabilities.json'
            data = json.loads(path.read_text())
            if mutation == 'missing':
                data['capabilities'] = []
            else:
                data['capabilities'][0]['lifecycle_status'] = 'quarantined'
            _write(path, data)

    if boundary == 'verification':
        change_admission()
        with pytest.raises(ValueError):
            verify_recovery_patch_package(
                project_dir=root, verification_dir=root / 'verification',
                patch_package={'status': 'prepared', 'patches': [{'kind': KEYS[0]}]})
    else:
        attempts = []

        def candidate(**kwargs):
            attempts.append(kwargs)
            change_admission()
            return {'status': 'prepared'}

        monkeypatch.setattr(recovery, 'synthesize_recovery_patch_package', candidate)
        with pytest.raises(ValueError):
            recovery._development_helper_extraction_package(
                execution_dir=root / 'execution', project_dir=root,
                target='writer.py:f', path_text='writer.py', operation_kinds=list(KEYS[:2]))
        assert len(attempts) == 1
    assert not (root / 'verification').exists()
