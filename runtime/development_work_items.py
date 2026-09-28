"""Explicit engineering tasks and evidence-backed assistant closure."""
from __future__ import annotations

import json
from pathlib import Path

from .source_refactor_analysis import digest
from .stage_finalization_workspace import _atomic_write, owned_path

KINDS = {'test_failure', 'architecture', 'documentation', 'provider', 'evaluation', 'feature'}


def validate_work_item(root: Path, task: dict) -> None:
    if (task.get('kind') not in KINDS or task.get('status') not in {'open', 'blocked', 'needs_verification', 'resolved'}
            or not isinstance(task.get('key'), str) or task.get('id') != 'work-' + digest(task['key'].encode())[:16]
            or not isinstance(task.get('blocking'), bool) or task.get('priority') not in {1, 2, 3}
            or not isinstance(task.get('dependencies'), list) or not isinstance(task.get('next_action'), str)):
        raise ValueError('invalid_engineering_task')
    path = owned_path(root.resolve(), task['path'])
    if path.name == 'config.json' or path.name.startswith('.env'):
        raise ValueError('private_task_path')
    if task['status'] == 'resolved' and not task.get('resolution', {}).get('evidence'):
        raise ValueError('resolved_handoff_requires_evidence')


def put_work_item(root: Path, *, key: str, kind: str, path: str, next_action: str,
                  blocking: bool = False, priority: int = 2, dependencies: list[str] | None = None) -> dict:
    from .development_handoff import read_queue, _queue_lock, _now
    root = root.resolve()
    task_id = 'work-' + digest(key.encode())[:16]
    with _queue_lock(root):
        queue = read_queue(root)
        existing = next((item for item in queue['tasks'] if item['id'] == task_id), None)
        task = {**(existing or {}), 'id': task_id, 'key': key, 'kind': kind, 'path': path,
                'owner': 'assistant', 'status': 'open', 'blocking': blocking, 'priority': priority,
                'dependencies': dependencies or [], 'next_action': next_action,
                'notes': (existing or {}).get('notes', []), 'updated_at': _now()}
        if existing and existing.get('resolution'):
            task['previous_resolution'] = task.pop('resolution')
        validate_work_item(root, task)
        known = {item['id'] for item in queue['tasks']}
        if task_id in task['dependencies'] or set(task['dependencies']) - known:
            raise ValueError('task_dependency_missing_or_self_reference')
        graph = {item['id']: item.get('dependencies', []) for item in queue['tasks']}
        graph[task_id] = task['dependencies']
        _check_cycle(graph, task_id, set())
        queue['tasks'] = [item for item in queue['tasks'] if item['id'] != task_id] + [task]
        _save(root, queue)
        return task


def close_work_item(root: Path, task_id: str, *, evidence: list[str], summary: str) -> dict:
    from .development_handoff import read_queue, _queue_lock, _now
    root = root.resolve()
    if not evidence or not summary.strip():
        raise ValueError('closure_requires_evidence_and_summary')
    receipts = []
    for name in evidence:
        path = owned_path(root, name)
        if not path.is_file():
            raise ValueError('closure_evidence_missing')
        receipts.append({'path': name, 'sha256': digest(path.read_bytes())})
    with _queue_lock(root):
        queue = read_queue(root)
        task = next(item for item in queue['tasks'] if item['id'] == task_id)
        if any(item['id'] in task.get('dependencies', []) and item['status'] != 'resolved' for item in queue['tasks']):
            raise ValueError('task_dependencies_unresolved')
        source = owned_path(root, task['path'])
        if task['kind'] == 'source_size' and source.is_file() and len(source.read_bytes().splitlines()) > task['limit']:
            raise ValueError('source_size_still_exceeded')
        task.update(status='resolved', next_action='none', resolution={
            'kind': 'assistant_review', 'summary': summary, 'evidence': evidence,
            'receipt_digests': receipts, 'resolved_at': _now(),
            'source_sha256': digest(source.read_bytes()) if source.is_file() else None})
        _save(root, queue)
        return task


def _check_cycle(graph, node, ancestors):
    if node in ancestors:
        raise ValueError('cyclic_task_dependencies')
    for child in graph.get(node, []):
        _check_cycle(graph, child, ancestors | {node})


def _save(root, queue):
    from .development_handoff import QUEUE_PATH
    encoded = (json.dumps(queue, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    if len(encoded) > 2_000_000:
        raise ValueError('handoff_queue_exceeds_budget')
    _atomic_write(owned_path(root, QUEUE_PATH), encoded)
