import json
from pathlib import Path

import pytest

from runtime.evaluation_input_readiness import input_readiness
from runtime.three_route_evaluation import _digest, freeze_manifest, manifest_drift_errors


def task(root, task_class='cli_utility', *, tree=False, constraints=True):
    directory = root / 'evaluation/task01_demo'
    directory.mkdir(parents=True)
    (directory / 'prompt.md').write_text(
        '# Task\n\n## Prompt\n\nImplement a transform.\n\n'
        + ('## Constraints\n\n- Sandbox only.\n\n' if constraints else '')
        + '## Expected Inputs\n\n- Project source.\n\n## Success Criteria\n\n- Tests pass.\n',
        encoding='utf-8')
    (directory / 'metrics.json').write_text(json.dumps({'task_class': task_class}))
    if tree:
        source = root / 'project'
        source.mkdir()
        (source / 'main.py').write_text('VALUE = 1\n')
        (directory / 'input.json').write_text(json.dumps({'kind': 'project_tree', 'path': 'project'}))
    return freeze_manifest(root, source_commit='abc')


def issues(root, manifest):
    return input_readiness(root, manifest)['tasks'][0]['issues']


def test_prompt_hash_consistency_is_not_project_input_readiness(tmp_path):
    manifest = task(tmp_path, 'project_analysis')
    assert manifest_drift_errors(tmp_path, manifest) == []
    assert issues(tmp_path, manifest) == ['project_contents_not_frozen']


def test_prompt_only_generation_is_supported_with_explicit_constraints(tmp_path):
    report = input_readiness(tmp_path, task(tmp_path))
    assert report['status'] == 'inputs_verified'
    assert report['verified_input_tasks'] == 1
    assert report['report_digest'] == _digest({k: v for k, v in report.items() if k != 'report_digest'})


def test_source_mutation_invalidates_readiness(tmp_path):
    manifest = task(tmp_path, 'project_analysis', tree=True)
    assert input_readiness(tmp_path, manifest)['status'] == 'inputs_verified'
    (tmp_path / 'project/main.py').write_text('VALUE = 2\n')
    assert 'task_snapshot_drift' in issues(tmp_path, manifest)


def test_ablation_supporting_source_is_bound_and_rechecked(tmp_path):
    from runtime.three_route_evaluation import _tree_digest
    task(tmp_path, 'architecture_hypothesis', tree=True)
    supporting = tmp_path / 'support'
    supporting.mkdir()
    (supporting / 'engine.py').write_text('value = 1')
    declaration = tmp_path / 'evaluation/task01_demo/input.json'
    declaration.write_text(json.dumps({'kind': 'project_tree', 'path': 'project',
        'supporting_input': {'path': 'support', 'tree_digest': _tree_digest(supporting)}}))
    manifest = freeze_manifest(tmp_path, source_commit='abc')
    assert issues(tmp_path, manifest) == []
    (supporting / 'engine.py').write_text('value = 2')
    assert 'input_support_drift' in issues(tmp_path, manifest)
    (supporting / 'config.json').write_text('private')
    assert 'input_support:private_input_file' in issues(tmp_path, manifest)


@pytest.mark.parametrize('task_class', ['architecture_hypothesis', 'configuration'])
def test_ablation_requires_a_concrete_workload(tmp_path, task_class):
    manifest = task(tmp_path, task_class, constraints=False)
    assert issues(tmp_path, manifest) == ['concrete_workload_not_frozen', 'constraints_not_frozen']


def test_private_source_is_rejected_before_hashing(tmp_path, monkeypatch):
    manifest = task(tmp_path, 'project_analysis', tree=True)
    private = tmp_path / 'project/config.json'
    private.write_text('private')
    original = Path.read_bytes
    def read(path):
        assert path != private, 'private file must never be read'
        return original(path)
    monkeypatch.setattr(Path, 'read_bytes', read)
    assert issues(tmp_path, manifest) == ['private_input_file']


def test_changed_declaration_cannot_redirect_hasher(tmp_path, monkeypatch):
    manifest = task(tmp_path, 'project_analysis', tree=True)
    (tmp_path / 'evaluation/task01_demo/input.json').write_text(
        json.dumps({'kind': 'project_tree', 'path': '../external'}))
    def fail(*args):
        pytest.fail('drifted declaration must not reach source hasher')
    monkeypatch.setattr('runtime.evaluation_input_readiness._freeze_task', fail)
    assert issues(tmp_path, manifest) == ['input_declaration_drift']


@pytest.mark.parametrize('path', ['../outside', 'C:/outside', 'project/../../outside', '.git'])
def test_unsafe_inputs_do_not_reach_hasher(tmp_path, monkeypatch, path):
    manifest = task(tmp_path, 'project_analysis', tree=True)
    manifest['tasks'][0]['input_spec']['path'] = path
    manifest['manifest_digest'] = _digest({k: v for k, v in manifest.items() if k != 'manifest_digest'})
    def fail(*args):
        pytest.fail('unsafe input must not reach source hasher')
    monkeypatch.setattr('runtime.evaluation_input_readiness._freeze_task', fail)
    assert input_readiness(tmp_path, manifest)['status'] == 'input_work_required'


def test_invalid_manifest_is_rejected_before_source_access(tmp_path):
    manifest = task(tmp_path)
    manifest['tasks'][0]['prompt_text'] = 'tampered'
    report = input_readiness(tmp_path, manifest)
    assert report['errors'] == ['manifest_digest_mismatch']
    assert report['tasks'] == []


def test_empty_tree_is_not_ready(tmp_path):
    manifest = task(tmp_path, 'project_analysis', tree=True)
    (tmp_path / 'project/main.py').unlink()
    assert issues(tmp_path, manifest) == ['input_project_empty']


def test_cli_bundle_rejects_unfrozen_project_before_writing(tmp_path, capsys):
    from argparse import Namespace
    from tools.three_route_evaluation import _bundle, _status
    manifest = task(tmp_path, 'project_analysis')
    (tmp_path / 'manifest.json').write_text(json.dumps(manifest))
    args = Namespace(manifest='manifest.json', receipts='receipts', output_dir='blind')
    assert _bundle(tmp_path, args, {}) == 2
    assert json.loads(capsys.readouterr().out)['status'] == 'inputs_not_ready'
    assert not (tmp_path / 'blind').exists()
    assert _status(tmp_path, args, {}) == 2
    report = json.loads(capsys.readouterr().out)
    assert report['status'] == 'inputs_not_ready'
    assert report['claim_eligible'] is False


def test_linked_definition_is_rejected_before_reading(tmp_path):
    manifest = task(tmp_path)
    original = tmp_path / 'evaluation/task01_demo/prompt.md'
    target = tmp_path / 'external.md'
    target.write_text('do not consume')
    original.unlink()
    try:
        original.symlink_to(target)
    except OSError:
        pytest.skip('symlink creation unavailable')
    assert issues(tmp_path, manifest) == ['linked_task_directory']
