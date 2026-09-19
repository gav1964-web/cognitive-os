"""Audit executable evaluation inputs separately from manifest self-consistency."""
from __future__ import annotations

import os
import re
from pathlib import Path

from .three_route_evaluation import (
    INPUT_SKIP_DIRS, _digest, _freeze_task, _tree_digest, validate_manifest,
)

PROJECT_CLASSES = {'project_analysis', 'documentation', 'sandbox_project_change'}
PROMPT_CLASSES = {'cli_utility', 'fastapi_service', 'negative'}
TASK_ID = re.compile(r'task[0-9]+_[a-z0-9_]+\Z')


def input_readiness(root: Path, manifest: dict) -> dict:
    """Read declared task sources only; never infer readiness from a prompt hash."""
    root = root.resolve()
    errors = validate_manifest(manifest)
    if errors:
        return _report(manifest, [], errors)
    rows = []
    for task in manifest['tasks']:
        task_id = task['task_id']
        issues = []
        if not TASK_ID.fullmatch(task_id):
            issues.append('unsafe_task_id')
        else:
            task_dir = root / 'evaluation' / task_id
            if any(_linked_path(root, task_dir / name) for name in ('prompt.md', 'metrics.json', 'input.json')):
                issues.append('linked_task_directory')
            elif not (task_dir / 'prompt.md').is_file() or not (task_dir / 'metrics.json').is_file():
                issues.append('task_definition_missing')
            else:
                issues.extend(_task_issues(root, task_dir, task))
        rows.append({'task_id': task_id, 'task_class': task['task_class'],
                     'input_kind': task.get('input_spec', {}).get('kind'),
                     'status': 'blocked' if issues else 'inputs_verified',
                     'issues': sorted(set(issues))})
    return _report(manifest, rows, [])


def _task_issues(root, task_dir, task):
    issues = []
    if not task.get('constraints'):
        issues.append('constraints_not_frozen')
    if not task.get('success_criteria'):
        issues.append('success_criteria_not_frozen')
    spec = task.get('input_spec') or {}
    kind = spec.get('kind')
    if kind == 'declared_prompt_inputs':
        if task['task_class'] in PROJECT_CLASSES:
            issues.append('project_contents_not_frozen')
        elif task['task_class'] not in PROMPT_CLASSES:
            issues.append('concrete_workload_not_frozen')
    elif kind == 'project_tree':
        issues.extend(_tree_issues(root, spec))
        support = spec.get('supporting_input')
        if support is not None:
            if not isinstance(support, dict) or not support.get('tree_digest'):
                issues.append('input_support_definition_incomplete')
            else:
                support_issues = _tree_issues(root, support)
                issues.extend('input_support:' + issue for issue in support_issues)
                if not support_issues and _tree_digest(root / support['path']) != support['tree_digest']:
                    issues.append('input_support_drift')
    else:
        issues.append('unsupported_input_kind')
    # Validate the on-disk declaration before the legacy hasher may follow it.
    import json
    declaration = task_dir / 'input.json'
    try:
        declared = json.loads(declaration.read_text(encoding='utf-8')) if declaration.is_file() else {
            'kind': 'declared_prompt_inputs', 'expected_inputs': task.get('expected_inputs', [])}
        expected = {key: value for key, value in spec.items() if key != 'tree_digest'}
        if declared != expected:
            issues.append('input_declaration_drift')
        elif not any(code.startswith(('input_', 'linked_', 'private_')) for code in issues):
            if _freeze_task(root, task_dir) != task:
                issues.append('task_snapshot_drift')
    except (OSError, ValueError, TypeError):
        issues.append('input_or_definition_unreadable')
    return issues


def _tree_issues(root, spec):
    from pathlib import PureWindowsPath
    value = spec.get('path')
    if not isinstance(value, str) or not value:
        return ['input_path_missing']
    path = Path(value)
    if path.is_absolute() or PureWindowsPath(value).drive or '..' in path.parts or '\\' in value:
        return ['input_path_not_workspace_relative']
    source = root / path
    if _linked_path(root, source) or not source.resolve().is_relative_to(root):
        return ['linked_input_path']
    if not source.is_dir():
        return ['input_project_missing']
    if any(_private(part) or part in INPUT_SKIP_DIRS for part in path.parts):
        return ['private_input_path']
    total, count = 0, 0
    try:
        def fail(error):
            raise error
        for current, dirs, files in os.walk(source, onerror=fail, followlinks=False):
            parent = Path(current)
            dirs[:] = [name for name in dirs if name not in INPUT_SKIP_DIRS]
            for name in [*dirs, *files]:
                candidate = parent / name
                if _private(name):
                    return ['private_input_file']
                if candidate.is_symlink() or _junction(candidate):
                    return ['linked_input_file']
            for name in files:
                count += 1
                total += (parent / name).stat().st_size
                if count > 10000 or total > 100_000_000:
                    return ['input_scan_budget_exceeded']
        if not count:
            return ['input_project_empty']
    except OSError:
        return ['input_project_unreadable']
    return []


def _private(name):
    return name == 'config.json' or name.startswith('.env') or name in {'.codex', '.agents', 'secret.key'}


def _junction(path):
    import stat
    attributes = getattr(path.lstat(), 'st_file_attributes', 0)
    return bool(attributes & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400))


def _linked_path(root, path):
    current = path
    while current != root:
        if current.is_symlink() or (current.exists() and _junction(current)):
            return True
        current = current.parent
    return False


def _report(manifest, rows, errors):
    ready = sum(row['status'] == 'inputs_verified' for row in rows)
    report = {'schema_version': 'evaluation_input_readiness.v1',
              'manifest_digest': manifest.get('manifest_digest'),
              'status': 'inputs_verified' if rows and ready == len(rows) and not errors else 'input_work_required',
              'task_count': len(manifest.get('tasks', [])), 'verified_input_tasks': ready,
              'blocked_input_tasks': len(rows) - ready, 'errors': errors, 'tasks': rows,
              'scope': 'Task definitions and declared inputs only; no execution, model comparability or independent judging claim.'}
    report['report_digest'] = _digest(report)
    return report
