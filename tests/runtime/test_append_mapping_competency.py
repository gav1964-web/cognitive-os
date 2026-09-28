"""Exact pre-extraction records/routing and admission of the second KB owner."""
import hashlib
import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest

from runtime.competency_knowledge import invoke_knowledge
from runtime.project_development_boundary_interpreter import (
    interpret_boundary, load_boundary_profiles, load_source_contrasts,
)

ROOT = Path(__file__).resolve().parents[2]
FROZEN = json.loads((ROOT / 'tests/fixtures/append_mapping_boundary_legacy.json').read_text(encoding='utf-8'))


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest()


def test_full_composite_catalogs_are_identical_after_record_extraction():
    assert _digest(load_boundary_profiles()) == FROZEN['profiles_sha256']
    assert _digest(load_source_contrasts()) == FROZEN['contrasts_sha256']


def test_owned_records_have_one_mutable_source_and_preserve_all_fields():
    profiles = invoke_knowledge('append_mapping', {'operation': 'boundary_profiles'})['records']
    contrasts = invoke_knowledge('append_mapping', {'operation': 'source_contrasts'})['records']
    assert len(profiles) == len(contrasts) == 1
    assert _digest(profiles[0]) == FROZEN['profile_sha256']
    assert _digest(contrasts[0]) == FROZEN['contrast_sha256']
    shared_profiles = json.loads((ROOT / 'knowledge/role_knowledge/project_development_boundary_profiles.json').read_text(encoding='utf-8'))
    assert {p['id'] for p in shared_profiles['profiles']} == {
        'cross_reducer_ambiguity', 'unsupported_reducer_shape', 'unsupported_reducer_shape_fallback'}
    assert json.loads((ROOT / 'knowledge/role_knowledge/project_development_source_contrasts.json').read_text(encoding='utf-8'))['contrasts'] == []


@pytest.mark.parametrize('case', FROZEN['contexts'])
def test_source_boundary_generic_fallback_and_unrelated_reducer_match_legacy(case):
    result = interpret_boundary(case['context'])
    assert result['id'] == case['expected_id']
    assert _digest(result) == case['result_sha256']


def test_registered_owner_does_not_promote_or_mutate_profile():
    original = invoke_knowledge('append_mapping', {'operation': 'boundary_profiles'})['records'][0]
    profile = deepcopy(original)
    result = invoke_knowledge('append_mapping', {'operation': 'decorate_profile', 'profile': profile})
    assert result['profile'] == original
    assert result['profile']['status'] == 'staged'
    assert result['profile']['evidence_state']['promotion_ready'] is False
    result['profile']['hypothesis']['confidence'] = 0
    assert profile == original
    assert invoke_knowledge('append_mapping', {'operation': 'boundary_profiles'})['records'][0] == original


@pytest.mark.parametrize('payload', [
    {'operation': 'decorate_profile'},
    {'operation': 'decorate_profile', 'profile': {'id': 'exception_pickle_reconstruction_boundary'}},
    {'operation': 'propose_patch', 'source': 'pass'},
    {'operation': 'boundary_profiles', 'source_apply': True},
])
def test_owner_contract_does_not_accept_foreign_profiles_or_execution(payload):
    with pytest.raises(Exception, match='append_mapping.input'):
        invoke_knowledge('append_mapping', payload)


@pytest.mark.parametrize('mutation,error', [('kb', 'identity_mismatch'), ('quarantine', 'not_active')])
def test_registry_blocks_changed_or_quarantined_owner(tmp_path, mutation, error):
    directory = tmp_path / 'plugins/append_mapping'
    shutil.copytree(ROOT / 'plugins/append_mapping', directory)
    records = json.loads((ROOT / 'registry/capabilities.json').read_text(encoding='utf-8'))
    if mutation == 'kb':
        path = directory / 'knowledge/project_development_boundary_profiles.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        data['profiles'][0]['status'] = 'active'
        path.write_text(json.dumps(data), encoding='utf-8')
    else:
        next(r for r in records['capabilities'] if r['id'] == 'append_mapping')['lifecycle_status'] = 'quarantined'
    (tmp_path / 'registry').mkdir()
    (tmp_path / 'registry/capabilities.json').write_text(json.dumps(records), encoding='utf-8')
    with pytest.raises(ValueError, match=error):
        invoke_knowledge('append_mapping', {'operation': 'boundary_profiles'}, root=tmp_path)
