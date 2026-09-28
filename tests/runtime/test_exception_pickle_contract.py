"""Registered consumers preserve proposal bytes and fail closed on admission."""
import hashlib
import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest

from plugins.exception_pickle.src.patch import exception_pickle_reconstruction_patch as owner_patch
from runtime import exception_pickle_contract as client
from runtime.programmer_exception_pickle_patch import exception_pickle_reconstruction_patch as legacy_patch

ROOT = Path(__file__).resolve().parents[2]
SOURCE = '''class Broken(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(str(code))
'''
RECIPE = {'required_constructor_inputs': ['code'], 'reconstruction_method': '__reduce__',
          'state_strategy': 'reuse_direct_assignments'}


@pytest.mark.parametrize('source', [
    SOURCE,
    SOURCE + '    def __reduce__(self):\n        return (type(self), (self.code,))\n',
    SOURCE.replace('code):', 'code, retryable=True):'),
    SOURCE.replace('self.code = code', 'self.code = str(code)'),
])
def test_registered_and_legacy_clients_preserve_owner_results(source):
    recipe = deepcopy(RECIPE)
    expected = owner_patch(source, class_name='Broken', recipe=recipe)
    assert client.propose_exception_pickle_patch(source, class_name='Broken', recipe=recipe) == expected
    assert legacy_patch(source, class_name='Broken', recipe=recipe) == expected
    assert recipe == RECIPE


@pytest.mark.parametrize('propose', [client.propose_exception_pickle_patch, legacy_patch])
@pytest.mark.parametrize('mutation,error', [
    ('kb', 'knowledge_provider_identity_mismatch'),
    ('lifecycle', 'knowledge_provider_not_active'),
])
def test_no_private_fallback_when_registration_rejects(tmp_path, propose, mutation, error):
    plugin = tmp_path / 'plugins/exception_pickle'
    shutil.copytree(ROOT / 'plugins/exception_pickle', plugin)
    registry = json.loads((ROOT / 'registry/capabilities.json').read_text(encoding='utf-8'))
    if mutation == 'kb':
        catalog = plugin / 'knowledge/exception_pickle_reconstruction_patterns.json'
        catalog.write_text(catalog.read_text(encoding='utf-8') + '\n', encoding='utf-8')
    else:
        next(row for row in registry['capabilities'] if row['id'] == 'exception_pickle')[
            'lifecycle_status'] = 'quarantined'
    (tmp_path / 'registry').mkdir()
    (tmp_path / 'registry/capabilities.json').write_text(json.dumps(registry), encoding='utf-8')
    with pytest.raises(ValueError, match=error):
        propose(SOURCE, class_name='Broken', recipe=RECIPE, competency_root=tmp_path)


@pytest.mark.parametrize('result', [
    {'status': 'ok', 'catalog': {}}, {'status': 'proposed', 'patch': None},
    {'status': 'not_applicable', 'patch': {'source': SOURCE}}, {'status': 'not_applicable'},
])
def test_wrong_operation_response_is_not_a_proposal_or_normal_refusal(monkeypatch, result):
    monkeypatch.setattr(client, 'invoke_knowledge', lambda *args, **kwargs: result)
    with pytest.raises(ValueError, match='invalid_exception_pickle_proposal_response'):
        client.propose_exception_pickle_patch(SOURCE, class_name='Broken', recipe=RECIPE)


def test_admission_failure_stops_authorized_runner_before_patch_and_native_replay(tmp_path, monkeypatch):
    from runtime.project_development_authorized_implementation import run_authorized_implementation
    from runtime.project_development_policy import load_project_development_policy
    from tests.runtime.test_project_development_authorized_implementation import _design

    project = tmp_path / 'project'
    project.mkdir()
    (project / 'pkg.py').write_text(SOURCE, encoding='utf-8')
    design = _design(hashlib.sha256((project / 'pkg.py').read_bytes()).hexdigest())
    design.update(target='pkg.py:Broken.__init__', implementation_recipe={
        **RECIPE, 'operator_id': 'preserve_exception_constructor_reconstruction'})
    calls = []

    def denied(*args, **kwargs):
        calls.append(kwargs['root'])
        raise ValueError('knowledge_provider_identity_mismatch')

    def unexpected_replay(**kwargs):
        pytest.fail('native replay must not run after admission failure')

    monkeypatch.setattr(client, 'invoke_knowledge', denied)
    monkeypatch.setattr('runtime.project_development_authorized_implementation.run_project_native_verification',
                        unexpected_replay)
    with pytest.raises(ValueError, match='knowledge_provider_identity_mismatch'):
        run_authorized_implementation(
            root=tmp_path, project_dir=project, execution_dir=tmp_path / 'execution',
            design=design, authorization_validation={'status': 'approved',
                'sandbox_implementation_authorized': True, 'source_apply_authorized': False},
            failing_nodeids=['tests/test_pkg.py::test_pickle'], policy=load_project_development_policy())
    assert calls == [ROOT]
    assert (project / 'pkg.py').read_text(encoding='utf-8') == SOURCE
    assert (tmp_path / 'execution/sandbox_project/pkg.py').read_text(encoding='utf-8') == SOURCE
