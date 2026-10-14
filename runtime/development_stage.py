"""Restore a bounded workspace context and record stage completion with evidence."""
from __future__ import annotations

import fnmatch
import json
import subprocess
import sys
import hashlib
from pathlib import Path

from .development_decisions import decision_context
from .development_handoff import active_tasks, sync_handoff, _now
from .repo_lint import _is_excluded
from .stage_finalization_workspace import _atomic_write, owned_path


def changed_paths(root: Path) -> list[str]:
    names = set()
    for args in (['diff', '--name-only', '-z', 'HEAD'], ['ls-files', '--others', '--exclude-standard', '-z']):
        result = subprocess.run(['git', '-C', str(root), *args], capture_output=True, timeout=30, check=True)
        names.update(result.stdout.decode('utf-8').split('\0'))
    return sorted(name for name in names if name and not _private_or_generated(root, name))


def begin_stage(root: Path, *, paths: list[str] | None = None) -> dict:
    from tools.project_context import load_manifest, context
    root = root.resolve()
    changed = changed_paths(root)
    focus = paths or changed
    for name in focus:
        owned_path(root, name)
        if _private_or_generated(root, name):
            raise ValueError('private_or_generated_context_path')
    manifest = load_manifest(root)
    selected, unmapped = set(), []
    for name in focus:
        matches = {key for key, spec in manifest['subsystems'].items()
                   if any(fnmatch.fnmatchcase(name, pattern) for pattern in spec['paths'])}
        selected.update(matches)
        if not matches:
            unmapped.append(name)
    pending = active_tasks(root)
    latest = root / 'artifacts/development/stage-latest.json'
    previous = json.loads(latest.read_text(encoding='utf-8')) if latest.is_file() else None
    payload = {
        'schema_version': 'development_stage.v1', 'phase': 'begin', 'observed_at': _now(),
        'changed_paths': changed, 'focus_paths': focus, 'unmapped_paths': unmapped,
        'context': context(root, manifest, sorted(selected)),
        'work_queue': sorted(pending, key=lambda row: (not row.get('blocking', row['kind'] == 'source_size'), row.get('priority', 1), row['id'])),
        'decisions': decision_context(root), 'previous_stage': previous,
        'recommended_tests': sorted({name for key in selected for name in manifest['subsystems'][key]['tests']}),
        'test_selection_scope': 'declared_navigation_only; review callers and use full tests for unmapped changes',
    }
    return payload


def finish_stage(root: Path, *, test_targets: list[str], pytest_plugins: list[str] | None = None,
                 timeout: int = 180, summary: str = '') -> dict:
    from .stage_finalization import finalize_stage
    from .stage_finalization_verification import verify_snapshot
    from .stage_finalization_workspace import inventory, snapshot, changed_files
    from .development_work_items import put_work_item
    import uuid
    root = root.resolve()
    if not test_targets:
        raise ValueError('stage_finish_requires_explicit_regression_scope')
    work = root / 'artifacts/development' / ('stage-' + uuid.uuid4().hex[:10])
    work.mkdir(parents=True)
    finalization = finalize_stage(root, repair=True, apply=True, test_targets=test_targets,
                                  pytest_plugins=pytest_plugins, timeout=timeout)
    handoff = sync_handoff(root, finalization, repair=True, test_targets=test_targets, pytest_plugins=pytest_plugins)
    verification, provenance = None, None
    if finalization['stage_complete']:
        before = inventory(root)
        source_record = json.dumps(before, sort_keys=True, separators=(',', ':')).encode('utf-8')
        _atomic_write(work / 'source-inventory.json', source_record)
        git_head = subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'],
                                  capture_output=True, text=True, timeout=30)
        provenance = {
            'inventory_path': str(work / 'source-inventory.json'),
            'inventory_sha256': hashlib.sha256(source_record).hexdigest(),
            'file_count': len(before), 'git_head': git_head.stdout.strip() or None,
            'python_executable': sys.executable, 'python_version': sys.version,
            'platform': sys.platform, 'pytest_plugins': pytest_plugins or [],
            'scope': 'source_paths inventory; excludes private config and generated artifacts',
            'trust_boundary': 'trusted-code subprocess copy; no OS sandbox',
        }
        snapshot(root, work / 'source', before)
        verification = verify_snapshot(work / 'source', work / 'checks', test_targets=test_targets,
                                       pytest_plugins=pytest_plugins, timeout=timeout)
        if changed_files(root, before) or changed_files(work / 'source', before):
            verification = {**verification, 'status': 'failed', 'reason': 'source_changed_during_verification'}
    passed = bool(verification and verification['status'] == 'passed')
    report = {'schema_version': 'development_stage.v1', 'phase': 'finish', 'finished_at': _now(),
              'status': 'completed' if finalization['stage_complete'] and passed and not handoff.get('blocking_pending') else 'needs_work',
              'summary': summary, 'test_targets': test_targets, 'verification': verification,
              'source_provenance': provenance,
              'finalization': finalization, 'handoff': handoff, 'receipt': str(work / 'report.json')}
    if verification and not passed:
        put_work_item(root, key='stage-regression:' + '|'.join(sorted(test_targets)), kind='test_failure',
                      path=test_targets[0], priority=1, blocking=True,
                      next_action='Inspect stage regression receipt: ' + str(work.relative_to(root) / 'report.json'))
    encoded = (json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    _atomic_write(work / 'report.json', encoded)
    _atomic_write(root / 'artifacts/development/stage-latest.json', encoded)
    return report


def _private_or_generated(root, name):
    path = Path(name)
    return (_is_excluded(root, root / name) or path.name == 'config.json' or path.name.startswith('.env')
            or any(part in {'.git', '.codex', '.agents'} for part in path.parts))
