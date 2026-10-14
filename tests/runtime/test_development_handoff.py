import json
import subprocess
import sys
from pathlib import Path

import pytest

from runtime.development_handoff import QUEUE_PATH, active_tasks, read_queue, sync_handoff
from runtime.stage_finalization import finalize_stage
from runtime.stage_finalization_workspace import inventory
from tests.runtime.test_stage_finalization import project, planner

CLI = Path(__file__).resolve().parents[2] / 'tools/finalize_stage.py'


def save(root, data):
    (root / QUEUE_PATH).write_text(json.dumps(data), encoding='utf-8')


def register(root):
    report = finalize_stage(root, max_lines=20)
    sync_handoff(root, report)
    return read_queue(root)


def test_repeated_audit_preserves_notes_and_does_not_rewrite_queue(tmp_path):
    root = project(tmp_path)
    data = register(root)
    data['tasks'][0]['notes'].append('Keep the public imports and pickle identity.')
    save(root, data)
    register(root)
    before = (root / QUEUE_PATH).read_bytes()
    modified = (root / QUEUE_PATH).stat().st_mtime_ns
    register(root)
    assert (root / QUEUE_PATH).read_bytes() == before
    assert (root / QUEUE_PATH).stat().st_mtime_ns == modified
    assert len(active_tasks(root)) == 1
    assert active_tasks(root)[0]['notes'] == data['tasks'][0]['notes']
    assert not (root / '.development-handoff.lock').exists()


@pytest.mark.parametrize('change', ['shrink', 'delete', 'looser_limit'])
def test_size_disappearance_or_looser_policy_cannot_close_manual_task(tmp_path, change):
    root = project(tmp_path)
    register(root)
    if change == 'shrink':
        (root / 'sample.py').write_text('pass\n')
    elif change == 'delete':
        (root / 'sample.py').unlink()
    report = finalize_stage(root, max_lines=400)
    sync_handoff(root, report)
    task = active_tasks(root)[0]
    assert task['status'] == ('open' if change == 'looser_limit' else 'needs_verification')
    assert task['limit'] == 20


def test_manual_resolution_is_retained_and_new_violation_reopens_same_id(tmp_path):
    root = project(tmp_path)
    data = register(root)
    task = data['tasks'][0]
    task.update(status='resolved', resolution={'kind': 'assistant_review', 'evidence': ['checks.xml']})
    save(root, data)
    (root / 'sample.py').write_text('pass\n')
    register(root)
    assert active_tasks(root) == []
    (root / 'sample.py').write_text('# regression\n' * 25)
    register(root)
    reopened = active_tasks(root)[0]
    assert reopened['id'] == task['id']
    assert reopened['previous_resolution'] == task['resolution']


def test_early_stop_persists_regression_scope_and_all_files_beyond_analysis_budget(tmp_path):
    root = tmp_path
    for index in range(10):
        (root / f'module_{index}.py').write_text('# oversize\n' * 25)
    report = finalize_stage(root, repair=True, max_lines=20, test_targets=['tests'])
    assert report['tasks_truncated'] and 'work_directory' not in report
    sync_handoff(root, report, repair=True, test_targets=['tests'])
    tasks = active_tasks(root)
    assert len(tasks) == 10
    assert tasks[0]['last_attempt']['test_targets'] == ['tests']
    assert tasks[0]['last_attempt']['reason'] == 'split_stage_into_at_most_three_oversized_modules'
    assert tasks[-1]['observation']['sha256']
    assert tasks[-1]['last_attempt']['reason'] == tasks[0]['last_attempt']['reason']


def test_failure_receipt_survives_scan_but_new_source_changes_next_action(tmp_path):
    root = project(tmp_path)
    report = finalize_stage(root, max_lines=20)
    report.update(status='needs_replanning', reason='llm_unavailable_or_invalid_response',
                  llm_failure_kind='http_500', work_directory=str(root / 'artifacts/stage-one'))
    report['provider_body'] = 'never-copy-this-secret'
    sync_handoff(root, report, repair=True, test_targets=['tests'])
    register(root)
    task = active_tasks(root)[0]
    assert 'bounded retry' in task['next_action']
    assert task['last_attempt']['receipt'] == 'artifacts/stage-one/report.json'
    assert 'never-copy-this-secret' not in (root / QUEUE_PATH).read_text()
    assert 'Return an explicitly' not in (root / QUEUE_PATH).read_text()
    with (root / 'sample.py').open('a') as stream:
        stream.write('# changed\n')
    register(root)
    task = active_tasks(root)[0]
    assert task['last_attempt']['source_sha256'] != task['observation']['sha256']
    assert 'bounded retry' not in task['next_action']


@pytest.mark.parametrize('apply', [False, True])
def test_only_applied_verified_patch_closes_task_without_mutating_snapshots(tmp_path, apply):
    root = project(tmp_path)
    register(root)
    report = finalize_stage(root, repair=True, apply=apply, max_lines=20, test_targets=['tests'],
                            planner=planner, work_root=tmp_path / 'work')
    assert report['verification']['status'] == 'passed'
    baseline = inventory(Path(report['work_directory']) / 'baseline')
    sandbox = inventory(Path(report['sandbox']))
    sync_handoff(root, report, repair=True, test_targets=['tests'])
    assert bool(active_tasks(root)) is not apply
    assert inventory(Path(report['work_directory']) / 'baseline') == baseline
    assert inventory(Path(report['sandbox'])) == sandbox
    if apply:
        task = read_queue(root)['tasks'][0]
        assert task['resolution']['source_sha256'] == task['observation']['sha256']


def test_development_and_api_only_pilot_leave_queue_untouched(tmp_path):
    root = project(tmp_path)
    report = finalize_stage(root, phase='development', max_lines=20)
    assert sync_handoff(root, report)['status'] == 'skipped_development_phase'
    finalize_stage(root, repair=True, max_lines=20, test_targets=['tests'],
                   planner=planner, work_root=tmp_path / 'pilot')
    assert not (root / QUEUE_PATH).exists()


def test_corrupt_queue_is_preserved_and_foreign_lock_is_not_removed(tmp_path):
    root = project(tmp_path)
    report = finalize_stage(root, max_lines=20)
    (root / QUEUE_PATH).write_text('{broken')
    with pytest.raises(ValueError):
        sync_handoff(root, report)
    assert (root / QUEUE_PATH).read_text() == '{broken'
    assert not (root / '.development-handoff.lock').exists()
    lock = root / '.development-handoff.lock'
    lock.write_text('another owner')
    with pytest.raises(FileExistsError):
        sync_handoff(root, report)
    assert lock.read_text() == 'another owner'


def test_queue_cannot_reference_external_source_or_resolve_without_evidence(tmp_path):
    root = project(tmp_path)
    data = register(root)
    task = data['tasks'][0]
    task['path'] = '../outside.py'
    save(root, data)
    with pytest.raises(ValueError):
        read_queue(root)
    task['path'] = 'sample.py'
    task['status'] = 'resolved'
    save(root, data)
    with pytest.raises(ValueError, match='requires_evidence'):
        read_queue(root)


def run_cli(root, *args):
    run = subprocess.run([sys.executable, '-S', str(CLI), '--root', str(root), *args],
                         capture_output=True, text=True, timeout=30)
    return run.returncode, json.loads(run.stdout)


def test_cli_saves_early_unsupported_case_and_blocks_unreviewed_manual_change(tmp_path):
    (tmp_path / 'sample.py').write_text('# oversized\n' * 401)
    code, report = run_cli(tmp_path, '--repair', '--test-target', 'tests')
    assert code == 1 and report['reason'] == 'unsupported_module_requires_design'
    assert report['handoff']['pending'] == 1
    (tmp_path / 'sample.py').write_text('pass\n')
    code, report = run_cli(tmp_path)
    assert code == 1 and report['status'] == 'needs_handoff_review'
    assert report['violations'] == [] and report['stage_complete'] is False
    assert active_tasks(tmp_path)[0]['status'] == 'needs_verification'


def test_cli_can_do_isolated_audit_and_fails_visibly_on_invalid_queue(tmp_path):
    (tmp_path / 'sample.py').write_text('pass\n')
    assert run_cli(tmp_path, '--no-handoff')[0] == 0
    assert not (tmp_path / QUEUE_PATH).exists()
    (tmp_path / QUEUE_PATH).write_text('{broken')
    code, report = run_cli(tmp_path)
    assert code == 1 and report['handoff']['status'] == 'failed'
    assert (tmp_path / QUEUE_PATH).read_text() == '{broken'
