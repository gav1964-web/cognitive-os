"""Bounded source snapshots and transactional application of verified edits."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .repo_lint import _is_excluded
from .source_refactor_analysis import digest

EXCLUDED_NAMES = {'config.json', '.stage-finalization.lock'}


def owned_path(root: Path, relative: str) -> Path:
    path = root / relative
    if (not relative or Path(relative).is_absolute() or '..' in Path(relative).parts
            or not path.resolve().is_relative_to(root.resolve())):
        raise ValueError('path_outside_workspace')
    current = path
    while current != root:
        if current.is_symlink():
            raise ValueError('symlink_not_supported')
        current = current.parent
    return path


def source_paths(root: Path) -> list[str]:
    if (root / '.git').exists():
        run = subprocess.run(['git', '-C', str(root), 'ls-files', '-z', '--cached',
                              '--others', '--exclude-standard'], capture_output=True, timeout=30, check=True)
        names = sorted(set(run.stdout.decode('utf-8').split('\0')) - {''})
    else:
        names = []
        for current, dirs, files in os.walk(root):
            parent = Path(current)
            dirs[:] = [d for d in dirs if not _is_excluded(root, parent / d)
                       and d not in {'node_modules', '.agents', '.codex'}]
            names.extend((parent / name).relative_to(root).as_posix() for name in files)
            if len(names) > 10_000:
                raise ValueError('snapshot_file_budget_exceeded')
    result = []
    for name in names:
        path = root / name
        if (_is_excluded(root, path) or path.name in EXCLUDED_NAMES or path.name.startswith('.env')
                or any(p in {'.agents', '.codex', 'node_modules'} for p in Path(name).parts)):
            continue
        path = owned_path(root, name)
        if path.is_file():
            result.append(name)
    if len(result) > 10_000:
        raise ValueError('snapshot_file_budget_exceeded')
    return sorted(result)


def inventory(root: Path) -> dict[str, str]:
    result, size = {}, 0
    for name in source_paths(root):
        path = owned_path(root, name)
        size += path.stat().st_size
        if size > 100_000_000:
            raise ValueError('snapshot_byte_budget_exceeded')
        result[name] = digest(path.read_bytes())
    return result


def snapshot(root: Path, destination: Path, expected: dict[str, str]) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    for name, expected_digest in expected.items():
        source = owned_path(root, name)
        target = owned_path(destination, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        data = source.read_bytes()
        if digest(data) != expected_digest:
            raise ValueError('source_changed_during_snapshot')
        target.write_bytes(data)
        shutil.copymode(source, target)


def write_edits(root: Path, edits: dict[str, bytes]) -> None:
    for name, content in edits.items():
        target = owned_path(root, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)


def changed_files(root: Path, expected: dict[str, str]) -> list[str]:
    current = inventory(root)
    return sorted(name for name in expected.keys() | current.keys() if expected.get(name) != current.get(name))


def apply_verified(root: Path, expected: dict[str, str], edits: dict[str, bytes]) -> None:
    """Apply only after a whole-source freshness check, rolling back partial writes."""
    lock = root / '.stage-finalization.lock'
    with lock.open('x', encoding='utf-8') as stream:
        stream.write('source finalization transaction\n')
    backups, written = {}, []
    try:
        if changed_files(root, expected):
            raise ValueError('source_changed_since_verification')
        for name in edits:
            path = owned_path(root, name)
            backups[name] = path.read_bytes() if path.exists() else None
        for name, data in edits.items():
            _atomic_write(owned_path(root, name), data)
            written.append(name)
    except BaseException:
        for name in reversed(written):
            path = owned_path(root, name)
            if backups[name] is None:
                path.unlink()
            else:
                _atomic_write(path, backups[name])
        raise
    finally:
        lock.unlink()


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix='.finalize-', dir=path.parent)
    try:
        with os.fdopen(handle, 'wb') as stream:
            stream.write(data)
        if path.exists():
            shutil.copymode(path, temporary)
        os.replace(temporary, path)
    finally:
        if Path(temporary).exists():
            Path(temporary).unlink()
