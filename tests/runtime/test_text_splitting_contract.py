"""Working text client, legacy alias, recipe ownership and refusal before write."""
import json
import shutil
from pathlib import Path

import pytest

from runtime import text_splitting_contract as client
from runtime.competency_knowledge import invoke_knowledge
from runtime.patch_synthesis_policy import splitlines_helper_recipe, load_patch_synthesis_policy
from runtime.programmer_patch_synthesizer_helper_extractors import _extract_splitlines_helper
from runtime.programmer_patch_synthesizer_recovery import synthesize_recovery_patch_package
from tests.runtime.test_text_splitting_owner import CASES, ROOT


@pytest.mark.parametrize('case', CASES, ids=[c['id'] for c in CASES])
def test_legacy_alias_and_registered_client_match_frozen(case):
    assert _extract_splitlines_helper(**case['request']) == case['patch']
    assert client.propose_text_splitting_patch(**case['request']) == case['patch']


def test_recipe_has_one_working_owner_and_preserves_entire_legacy_policy():
    legacy = json.loads((ROOT / 'tests/fixtures/append_mapping_policy_legacy.json').read_text(encoding='utf-8'))
    assert load_patch_synthesis_policy() == legacy
    assert splitlines_helper_recipe() == legacy['recipes']['extract_splitlines_helper']
    assert 'extract_splitlines_helper' not in load_patch_synthesis_policy(ROOT / 'config/patch_synthesis_policy.json')['recipes']


@pytest.mark.parametrize('mutation,error', [('kb','identity_mismatch'), ('quarantine','not_active')])
def test_owner_admission_denies_changed_or_quarantined_plugin(tmp_path, mutation, error):
    destination = tmp_path / 'plugins/text_splitting'
    shutil.copytree(ROOT / 'plugins/text_splitting', destination)
    records = json.loads((ROOT / 'registry/capabilities.json').read_text(encoding='utf-8'))
    if mutation == 'kb':
        p = destination / 'knowledge/patch_recipes.json'
        d = json.loads(p.read_text(encoding='utf-8'))
        d['recipes'][0]['recipe']['required_candidate_symbol'] = 'different_symbol'
        p.write_text(json.dumps(d), encoding='utf-8')
    else:
        next(r for r in records['capabilities'] if r['id']=='text_splitting')['lifecycle_status'] = 'quarantined'
    (tmp_path / 'registry').mkdir()
    (tmp_path / 'registry/capabilities.json').write_text(json.dumps(records), encoding='utf-8')
    with pytest.raises(ValueError, match=error):
        invoke_knowledge('text_splitting', {'operation':'patch_recipes'}, root=tmp_path)


@pytest.mark.parametrize('admitted', [True, False])
def test_recovery_gate_and_invalid_result_prevent_writes(tmp_path, monkeypatch, admitted):
    source = CASES[0]['request']['source'].encode('utf-8')
    project = tmp_path / 'project'
    project.mkdir()
    (project / 'writer.py').write_bytes(source)
    calls = []
    def forged(capability, payload, **kwargs):
        calls.append((capability, payload['operation'], kwargs['root']))
        return {'status':'ok','proposal':{'schema_version':'helper_proposal.v1','status':'proposed',
            'source':'pass','operation_details':{'file':'../outside.py'},'reason':None}}
    monkeypatch.setattr(client, 'invoke_knowledge', forged)
    args = dict(execution_dir=tmp_path / 'execution', project_dir=project, recovery_route={
        'status':'bounded_rework_ready','architect_reentry_gate':{'status':'accepted_for_bounded_rework' if admitted else 'blocked'},
        'research_hypothesis':{'hypothesis_type':'pure_core_with_effect_adapters',
            'origin_target':'writer.py:load_lines','proposed_target':'writer.py:split_lines'}})
    if admitted:
        with pytest.raises(ValueError, match='overrides_coordinator'):
            synthesize_recovery_patch_package(**args)
        assert calls == [('text_splitting','propose_helper',ROOT)]
        assert (tmp_path / 'execution/recovery_patch_sandbox/project/writer.py').read_bytes() == source
    else:
        assert synthesize_recovery_patch_package(**args)['reason'] == 'recovery_route_not_admitted'
        assert calls == []
    assert (project / 'writer.py').read_bytes() == source
