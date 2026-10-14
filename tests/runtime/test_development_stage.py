import json
from pathlib import Path

import pytest

from runtime.development_decisions import decision_context, remember_decision
from runtime.development_handoff import active_tasks, sync_handoff
from runtime.development_stage import begin_stage, finish_stage
from runtime.development_work_items import put_work_item, close_work_item
from runtime.stage_finalization import finalize_stage
from tests.tools.test_project_context import fixture_manifest


def task(root, key='ci', **kwargs):
    return put_work_item(root, key=key, kind='test_failure', path='sample.py',
                         next_action='Run regression tests and inspect failing contract.', **kwargs)


def test_backlog_is_preserved_and_only_explicit_blockers_block_finalization(tmp_path):
    (tmp_path / 'sample.py').write_text('pass\n')
    backlog = task(tmp_path)
    result = sync_handoff(tmp_path, finalize_stage(tmp_path))
    assert result['pending'] == 1 and result['blocking_pending'] == 0
    task(tmp_path, blocking=True)
    result = sync_handoff(tmp_path, finalize_stage(tmp_path))
    assert result['pending'] == result['blocking_pending'] == 1
    assert active_tasks(tmp_path)[0]['id'] == backlog['id']


def test_dependencies_need_resolution_and_cycles_are_rejected(tmp_path):
    (tmp_path / 'sample.py').write_text('pass\n')
    first = task(tmp_path, 'first')
    second = task(tmp_path, 'second', dependencies=[first['id']])
    (tmp_path / 'checks.json').write_text('{"status": "passed"}')
    with pytest.raises(ValueError, match='cyclic'):
        task(tmp_path, 'first', dependencies=[second['id']])
    with pytest.raises(ValueError, match='dependencies_unresolved'):
        close_work_item(tmp_path, second['id'], evidence=['checks.json'], summary='Reviewed.')
    close_work_item(tmp_path, first['id'], evidence=['checks.json'], summary='Reviewed first.')
    close_work_item(tmp_path, second['id'], evidence=['checks.json'], summary='Reviewed second.')
    assert active_tasks(tmp_path) == []


def test_decision_becomes_stale_after_source_edit_and_rejects_private_context(tmp_path):
    (tmp_path / 'sample.py').write_text('pass\n')
    remember_decision(tmp_path, key='api', decision='Preserve imports.', rationale='Public callers depend on them.',
                       paths=['sample.py'], reconsider_when='Public API version changes.')
    assert decision_context(tmp_path)[0]['status'] == 'current'
    (tmp_path / 'sample.py').write_text('changed = True\n')
    assert decision_context(tmp_path)[0]['changed_paths'] == ['sample.py']
    with pytest.raises(ValueError, match='private_path'):
        remember_decision(tmp_path, key='unsafe', decision='bad', rationale='bad',
                           paths=['config.json'], reconsider_when='bad')


def test_begin_restores_changes_tasks_and_explicit_unmapped_paths(tmp_path, monkeypatch):
    manifest = fixture_manifest(tmp_path)
    manifest['schema_version'] = 'project_context.v1'
    (tmp_path / 'docs/architecture').mkdir(parents=True)
    (tmp_path / 'docs/architecture/subsystems.json').write_text(json.dumps(manifest))
    monkeypatch.setattr('runtime.development_stage.changed_paths', lambda _: ['source/main.py', 'unknown.py'])
    (tmp_path / 'config.json').write_text('secret-content')
    result = begin_stage(tmp_path)
    assert result['unmapped_paths'] == ['unknown.py']
    assert list(result['context']['subsystems']) == ['sample']
    assert 'secret-content' not in json.dumps(result)


@pytest.mark.parametrize('passing', [False, True])
def test_finish_runs_real_regressions_even_when_size_is_already_valid(tmp_path, passing):
    (tmp_path / 'sample.py').write_text('def answer(): return 42\n')
    (tmp_path / 'test_sample.py').write_text('from sample import answer\ndef test_answer(): assert answer() == ' + ('42' if passing else '0'))
    report = finish_stage(tmp_path, test_targets=['test_sample.py'], summary='Verify behavior.')
    assert report['status'] == ('completed' if passing else 'needs_work')
    assert Path(report['receipt']).is_file()
    assert bool(active_tasks(tmp_path)) is not passing
    assert report['verification']['collected']
    provenance = report['source_provenance']
    import hashlib
    raw = Path(provenance['inventory_path']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == provenance['inventory_sha256']
    assert json.loads(raw)['sample.py'] == hashlib.sha256((tmp_path / 'sample.py').read_bytes()).hexdigest()
    assert provenance['trust_boundary'] == 'trusted-code subprocess copy; no OS sandbox'
