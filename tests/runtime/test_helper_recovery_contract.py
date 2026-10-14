"""Full legacy recovery packages and untrusted result admission before writes."""
import json
from pathlib import Path

import pytest

from runtime import append_mapping_contract as client
from runtime.helper_extraction_dispatch import propose_helper_extraction
from runtime.programmer_patch_synthesizer_recovery import synthesize_recovery_patch_package

ROOT = Path(__file__).resolve().parents[2]
CASES = json.loads((ROOT / 'tests/fixtures/helper_recovery_packages_legacy.json').read_text(encoding='utf-8'))['cases']


@pytest.mark.parametrize('case', CASES, ids=[c['id'] for c in CASES])
def test_full_recovery_package_matches_frozen_legacy(tmp_path, case):
    project = tmp_path / 'project'
    project.mkdir()
    original = case['source'].encode('utf-8')
    (project / 'writer.py').write_bytes(original)
    result = synthesize_recovery_patch_package(
        execution_dir=tmp_path / 'execution', project_dir=project, recovery_route=case['route'])
    if 'sandbox_project' in result:
        assert (Path(result['sandbox_project']) / 'writer.py').read_bytes() == case['patched_source'].encode('utf-8')
        result['sandbox_project'] = '<sandbox>'
    assert result == case['package']
    assert (project / 'writer.py').read_bytes() == original


@pytest.mark.parametrize('mutation', ['forged_path', 'bad_source', 'applied', 'syntax_error'])
def test_invalid_owner_output_never_writes_candidate(tmp_path, monkeypatch, mutation):
    case = CASES[0]
    project = tmp_path / 'project'
    project.mkdir()
    original = case['source'].encode('utf-8')
    (project / 'writer.py').write_bytes(original)
    proposal = {'schema_version':'helper_proposal.v1','status':'proposed','source':'def broken(:',
                'operation_details':{},'reason':None}
    if mutation == 'forged_path': proposal['operation_details']['file'] = '../outside.py'
    elif mutation == 'bad_source': proposal['source'] = None
    elif mutation == 'applied': proposal['status'] = 'applied'
    calls = []
    def supplied(capability, payload, **kwargs):
        calls.append((capability, payload['operation'], kwargs['root']))
        return {'status':'ok','proposal':proposal}
    monkeypatch.setattr(client, 'invoke_knowledge', supplied)
    args = dict(execution_dir=tmp_path / 'execution', project_dir=project, recovery_route=case['route'])
    if mutation == 'syntax_error':
        assert synthesize_recovery_patch_package(**args)['reason'] == 'synthesized_source_does_not_compile'
    else:
        with pytest.raises(ValueError): synthesize_recovery_patch_package(**args)
    assert calls == [('append_mapping', 'propose_helper', ROOT)]
    assert (project / 'writer.py').read_bytes() == original
    assert (tmp_path / 'execution/recovery_patch_sandbox/project/writer.py').read_bytes() == original
    assert not (tmp_path / 'execution/recovery_patch_sandbox/outside.py').exists()


def test_unknown_dispatch_is_not_dynamic_execution():
    assert propose_helper_extraction('pass', origin_symbol='f', proposed_symbol='g',
                                     recipe={'operation_kind':'os.system'}) is None
