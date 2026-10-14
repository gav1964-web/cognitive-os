"""Legacy proposal bytes and sandbox boundaries across registered extraction."""
import json
from pathlib import Path

import pytest

from runtime import append_mapping_contract as client
from runtime.programmer_patch_synthesizer_helper_extractors import _extract_append_mapping_helper as legacy
from runtime.programmer_patch_synthesizer_recovery import synthesize_recovery_patch_package

ROOT = Path(__file__).resolve().parents[2]
FROZEN = json.loads((ROOT / 'tests/fixtures/append_mapping_extractor_legacy.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('case', FROZEN['cases'])
def test_proposal_and_refusal_match_legacy_exactly(case):
    assert client.propose_append_mapping_helper(**case['request']) == case['patch']
    assert legacy(**case['request']) == case['patch']
    if case['patch'] is not None:
        original, patched = {}, {}
        exec(case['request']['source'], original)
        exec(case['patch']['source'], patched)
        for rows in [[], [' alice ', '', ' bob']]:
            assert original['normalize_rows'](rows) == patched['normalize_rows'](rows)


@pytest.mark.parametrize('admitted', [True, False])
def test_recovery_gate_and_admission_failure_prevent_patch_write(tmp_path, monkeypatch, admitted):
    source = FROZEN['cases'][0]['request']['source']
    project = tmp_path / 'project'
    project.mkdir()
    (project / 'writer.py').write_text(source, encoding='utf-8')
    calls = []

    def denied(*args, **kwargs):
        calls.append(kwargs['root'])
        raise ValueError('knowledge_provider_identity_mismatch')

    monkeypatch.setattr(client, 'invoke_knowledge', denied)
    request = dict(execution_dir=tmp_path / 'execution', project_dir=project,
        recovery_route={'status':'bounded_rework_ready',
            'architect_reentry_gate':{'status':'accepted_for_bounded_rework' if admitted else 'blocked'},
            'research_hypothesis':{'hypothesis_type':'pure_core_with_effect_adapters',
                'origin_target':'writer.py:normalize_rows','proposed_target':'writer.py:normalize_record'}})
    if admitted:
        with pytest.raises(ValueError, match='identity_mismatch'):
            synthesize_recovery_patch_package(**request)
        assert calls == [ROOT]
        sandboxes = list((tmp_path / 'execution').rglob('writer.py'))
        assert len(sandboxes) == 1 and sandboxes[0].read_text(encoding='utf-8') == source
    else:
        assert synthesize_recovery_patch_package(**request)['reason'] == 'recovery_route_not_admitted'
        assert calls == []
    assert (project / 'writer.py').read_text(encoding='utf-8') == source


@pytest.mark.parametrize('result', [{'status':'ok','records':[]}, {'status':'proposed','patch':None}, {'status':'not_applicable'}])
def test_wrong_response_is_not_normal_non_applicability(monkeypatch, result):
    monkeypatch.setattr(client, 'invoke_knowledge', lambda *a, **k:result)
    with pytest.raises(ValueError, match='invalid_append_mapping_proposal_response'):
        client.propose_append_mapping_helper(**FROZEN['cases'][0]['request'])
