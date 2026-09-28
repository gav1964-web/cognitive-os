"""Persistent assistant work queue; source-size facts are not regression proof."""
from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .repo_lint import _is_excluded
from .source_refactor_analysis import digest
from .stage_finalization_workspace import _atomic_write, owned_path

QUEUE_PATH = 'DEVELOPMENT_TASKS.json'
SCHEMA = 'development_handoff.v1'
STATES = {'open', 'needs_verification', 'resolved'}


def read_queue(root: Path) -> dict:
    path = owned_path(root.resolve(), QUEUE_PATH)
    if not path.exists():
        return {'schema_version': SCHEMA, 'tasks': []}
    if path.stat().st_size > 2_000_000:
        raise ValueError('handoff_queue_exceeds_budget')
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('schema_version') != SCHEMA or not isinstance(data.get('tasks'), list):
        raise ValueError('invalid_handoff_queue')
    seen = set()
    for task in data['tasks']:
        if isinstance(task, dict) and task.get('kind') != 'source_size':
            from .development_work_items import validate_work_item
            validate_work_item(root, task)
            if task['id'] in seen:
                raise ValueError('duplicate_handoff_id')
            seen.add(task['id'])
            continue
        if (not isinstance(task, dict) or not isinstance(task.get('path'), str)
                or task.get('status') not in STATES or task.get('kind') != 'source_size'
                or not isinstance(task.get('limit'), int) or task['limit'] < 10):
            raise ValueError('invalid_handoff_task')
        _source_path(root.resolve(), task['path'])
        if task.get('id') != _task_id(task['path']) or task['id'] in seen:
            raise ValueError('invalid_or_duplicate_handoff_id')
        seen.add(task['id'])
        if task['status'] == 'resolved':
            resolution = task.get('resolution')
            evidence = resolution.get('evidence') if isinstance(resolution, dict) else None
            if not isinstance(evidence, list) or not evidence or not all(isinstance(p, str) and p.strip() for p in evidence):
                raise ValueError('resolved_handoff_requires_evidence')
    return data


def active_tasks(root: Path) -> list[dict]:
    return [task for task in read_queue(root)['tasks'] if task['status'] != 'resolved']


def sync_handoff(root: Path, report: dict, *, repair: bool = False,
                 test_targets: list[str] | None = None, pytest_plugins: list[str] | None = None) -> dict:
    """Run only after finalization returns, never within verification snapshots."""
    root = root.resolve()
    if report.get('phase') != 'final':
        return {'status': 'skipped_development_phase', 'path': QUEUE_PATH}
    if Path(report['root']).resolve() != root:
        raise ValueError('handoff_report_root_mismatch')
    with _queue_lock(root):
        data = read_queue(root)
        original = json.dumps(data, sort_keys=True)
        tasks = {task['path'] if task['kind'] == 'source_size' else task['id']: task for task in data['tasks']}
        analyses = {task['path']: task for task in report.get('tasks', [])}
        reported_paths = {violation['path'] for violation in report['violations']}
        for violation in report['violations']:
            name = violation['path']
            _source_path(root, name)
            tasks.setdefault(name, {
                'id': _task_id(name), 'kind': 'source_size', 'path': name,
                'owner': 'assistant', 'status': 'open', 'limit': violation['limit'],
                'first_seen': _now(), 'notes': [],
            })
        for name, task in sorted(tasks.items()):
            if task['kind'] != 'source_size':
                continue
            previous = json.dumps(task, sort_keys=True)
            observation = _observe(root, name)
            task['observation'] = observation
            # A looser later run must not silently erase the original obligation.
            task['limit'] = min(task['limit'], report['max_python_lines'])
            analysis = analyses.get(name)
            if analysis:
                task['analysis'] = {key: analysis[key] for key in ('sha256', 'reason', 'rejected') if key in analysis}
            if repair and name in reported_paths:
                task['last_attempt'] = _attempt(report, analysis or observation, test_targets, pytest_plugins)
            oversized = observation.get('line_count', 0) > task['limit']
            if oversized:
                if task['status'] == 'resolved':
                    task['previous_resolution'] = task.pop('resolution')
                task['status'] = 'open'
                task['next_action'] = _next_action(task)
            elif _verified_apply(root, report, name, observation):
                task.update(status='resolved', next_action='none', resolution={
                    'kind': 'verified_automatic_extraction', 'source_sha256': observation['sha256'],
                    'evidence': [_reference(root, str(Path(report['work_directory']) / 'report.json'))],
                    'test_targets': test_targets or [], 'resolved_at': _now(),
                })
            elif task['status'] != 'resolved':
                task['status'] = 'needs_verification'
                task['next_action'] = ('Review the changed or removed module and its callers, run relevant regression '
                                       'tests, then record evidence and resolve this task; size alone is insufficient.')
            if json.dumps(task, sort_keys=True) != previous:
                task['updated_at'] = _now()
        data['tasks'] = sorted(tasks.values(), key=lambda item: item['path'])
        if json.dumps(data, sort_keys=True) != original or not (root / QUEUE_PATH).exists():
            encoded = (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
            if len(encoded) > 2_000_000:
                raise ValueError('handoff_queue_exceeds_budget')
            _atomic_write(owned_path(root, QUEUE_PATH), encoded)
        pending = [task for task in data['tasks'] if task['status'] != 'resolved']
        return {'status': 'saved', 'path': QUEUE_PATH, 'pending': len(pending),
                'blocking_pending': sum(task.get('blocking', task['kind'] == 'source_size') for task in pending),
                'task_ids': [task['id'] for task in pending]}


@contextmanager
def _queue_lock(root: Path):
    lock = owned_path(root, '.development-handoff.lock')
    handle = lock.open('x', encoding='utf-8')
    try:
        yield
    finally:
        handle.close()
        lock.unlink()


def _task_id(name: str) -> str:
    return 'size-' + digest(name.encode('utf-8'))[:16]


def _source_path(root: Path, name: str) -> Path:
    path = owned_path(root, name)
    if path.suffix != '.py' or Path(name).as_posix() != name:
        raise ValueError('handoff_requires_relative_python_path')
    return path


def _observe(root: Path, name: str) -> dict:
    path = _source_path(root, name)
    if _is_excluded(root, path):
        return {'state': 'outside_current_scope'}
    if not path.exists():
        return {'state': 'missing'}
    raw = path.read_bytes()
    return {'state': 'present', 'sha256': digest(raw), 'line_count': len(raw.splitlines())}


def _attempt(report: dict, analysis: dict, targets, plugins) -> dict:
    # No provider body, prompt, source text or full test output enters the task queue.
    reason = report.get('reason', report['status']).split(':', 1)[0]
    return {'source_sha256': analysis.get('sha256'), 'status': report['status'], 'reason': reason,
            'llm_failure_kind': report.get('llm_failure_kind'),
            'test_targets': targets or [], 'pytest_plugins': plugins or [],
            'baseline_status': report.get('baseline', {}).get('status'),
            'verification_status': report.get('verification', {}).get('status'),
            'checks': report.get('checks', {}),
            'receipt': _reference(Path(report['root']), str(Path(report['work_directory']) / 'report.json'))
                       if report.get('work_directory') else None}


def _reference(root: Path, value: str) -> str:
    path = Path(value).resolve()
    return path.relative_to(root.resolve()).as_posix() if path.is_relative_to(root.resolve()) else str(path)


def _verified_apply(root: Path, report: dict, name: str, observation: dict) -> bool:
    if (not report.get('source_applied') or name not in report.get('patch_files', [])
            or report.get('verification', {}).get('status') != 'passed'
            or not report.get('checks') or not all(report['checks'].values())
            or observation.get('state') != 'present'):
        return False
    sandbox = Path(report['sandbox']).resolve()
    return digest(owned_path(sandbox, name).read_bytes()) == observation['sha256']


def _next_action(task: dict) -> str:
    attempt = task.get('last_attempt', {})
    if attempt.get('source_sha256') == task['observation'].get('sha256'):
        reason = attempt.get('reason')
        if reason == 'llm_unavailable_or_invalid_response':
            return 'Inspect the L4.5 transport receipt; make one bounded retry or perform the refactor directly.'
        if reason == 'baseline_verification_failed':
            return 'Diagnose and fix baseline tests before attempting a source split.'
        if reason == 'verification_or_source_invariant_failed':
            return 'Inspect the failed checks and patch; preserve the failing contract in a manual refactor.'
        if attempt.get('status') == 'verified_patch':
            return 'Review the saved patch and rerun verified application against the current source.'
    return ('Inspect module responsibilities and callers, choose a regression scope, and split the module; '
            'use ordinary assistant refactoring for structures unsupported by the automatic operator.')


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')
