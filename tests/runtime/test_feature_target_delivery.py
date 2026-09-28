"""Selected deployment keeps local state and enforces the reviewed source chain."""
import json
import sys
from pathlib import Path

import pytest

from runtime.feature_delivery import deliver_feature
from runtime.feature_target_delivery import compose_deliveries, deliver_to_target
from runtime.feature_workspace import copy_source, digest, install, inventory
from tests.runtime.test_feature_development import project, fake_chat, run


@pytest.fixture
def bundle(project, tmp_path):
    checkpoint = tmp_path / 'first'
    assert run(project, checkpoint, chat=fake_chat(project))['status'] == 'verified'
    work = tmp_path / 'bundle'
    assert deliver_feature(project=project, checkpoints=[checkpoint / 'run'], work=work,
        python=Path(sys.executable))['status'] == 'verified'
    return work / 'report.json'


def test_install_exact_bundle_keeps_local_state(project, tmp_path, bundle):
    target = tmp_path / 'working'
    copy_source(project, target, inventory(project))
    project = target
    (project / 'config.json').write_text('{"local":true}')
    (project / 'runs').mkdir()
    (project / 'runs/runtime.json').write_text('{"running":true}')
    result = deliver_to_target(target=project, deliveries=[bundle], work=tmp_path / 'target',
                               python=Path(sys.executable), apply=True)
    assert result['status'] == 'installed'
    assert (project / 'config.json').read_text() == '{"local":true}'
    assert (project / 'runs/runtime.json').read_text() == '{"running":true}'
    assert (project / 'engine.py').read_bytes() == (bundle.parent / 'project/engine.py').read_bytes()


@pytest.mark.parametrize('damage', ['source', 'collision', 'review'])
def test_changed_dependency_or_collision_never_writes(project, tmp_path, bundle, damage):
    target = tmp_path / 'working'
    copy_source(project, target, inventory(project))
    project = target
    if damage == 'source':
        (project / 'engine.py').write_text('# concurrent change\n')
    elif damage == 'collision':
        (project / 'tests/test_labels.py').write_text('# unrelated work\n')
    else:
        reviewer = tmp_path / 'first/run/reviewer.json'
        content = json.loads(reviewer.read_text()); content['decision'] = 'reject'
        reviewer.write_text(json.dumps(content))
    before = inventory(project)
    with pytest.raises(ValueError):
        deliver_to_target(target=project, deliveries=[bundle], work=tmp_path / 'target',
                          python=Path(sys.executable), apply=True)
    assert inventory(project) == before


def test_fixture_bridge_requires_exact_explicit_input(project, tmp_path, bundle):
    baseline = tmp_path / 'second-source'
    copy_source(bundle.parent / 'project', baseline, inventory(bundle.parent / 'project'))
    fixture = baseline / 'tests/fixtures/input.json'
    fixture.parent.mkdir(); fixture.write_text('{"value":0}')
    delegate = fake_chat(baseline)

    def chat(messages, *, config):
        if config.provider_label == 'feature:spec_writer':
            return {'status': 'ready', 'acceptance': ['zero'], 'limitations': ['fixture only'], 'environment': {},
                    'tests': [{'path': 'tests/test_zero.py', 'content':
                        'from engine import display\ndef test_zero():\n    assert display(0) == "zero"\n'}],
                    'regression_tests': ['tests/test_existing.py', 'tests/test_labels.py']}
        if config.provider_label == 'feature:programmer':
            return {'status': 'ready', 'edits': [{'path': 'engine.py',
                'source_sha256': digest((baseline / 'engine.py').read_bytes()),
                'replacements': [{'old': 'else str(value)',
                                  'new': 'else "zero" if value == 0 else str(value)'}]}]}
        return delegate(messages, config=config)

    second = tmp_path / 'second'
    assert run(baseline, second, chat=chat)['status'] == 'verified'
    second_bundle = tmp_path / 'second-bundle'
    assert deliver_feature(project=baseline, checkpoints=[second / 'run'], work=second_bundle,
                           python=Path(sys.executable))['status'] == 'verified'
    deliveries = [bundle, second_bundle / 'report.json']
    with pytest.raises(ValueError, match='unapproved_data_input'):
        compose_deliveries(deliveries, {})
    with pytest.raises(ValueError, match='unapproved_data_input'):
        compose_deliveries(deliveries, {'tests/fixtures/input.json': 'wrong'})
    target = tmp_path / 'working'
    copy_source(project, target, inventory(project))
    result = deliver_to_target(target=target, deliveries=deliveries, work=tmp_path / 'target',
        python=Path(sys.executable), data_inputs={'tests/fixtures/input.json': digest(fixture.read_bytes())},
        apply=True)
    assert result['status'] == 'installed'
    assert result['verification']['counts']['passed'] == 3
    assert (target / 'tests/fixtures/input.json').read_bytes() == fixture.read_bytes()


def test_selected_transaction_rolls_back_after_write_failure(project, tmp_path, monkeypatch):
    import runtime.feature_workspace as workspace
    original = inventory(project)
    write = workspace._atomic_write

    def fail_second(path, data):
        if path == project / 'new.py':
            raise OSError('disk failure')
        return write(path, data)

    monkeypatch.setattr(workspace, '_atomic_write', fail_second)
    with pytest.raises(OSError, match='disk failure'):
        install(project, original, {'engine.py': b'# changed\n', 'new.py': b'# new\n'},
                tmp_path / 'backup', selected_source=True)
    assert inventory(project) == original
    assert not (project / '.cos-feature.lock').exists()
