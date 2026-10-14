"""Copy explicitly selected evaluation sources without changing their originals."""
from __future__ import annotations

import hashlib
import stat
from pathlib import Path, PureWindowsPath


def copy_input_snapshot(source: Path, destination: Path, names: list[str]) -> dict:
    source, destination = source.resolve(), destination.absolute()
    if destination.exists():
        raise ValueError('snapshot_destination_exists')
    if not names or len(names) > 10000 or len(set(names)) != len(names):
        raise ValueError('invalid_snapshot_selection')
    files, total = {}, 0
    for name in sorted(names):
        path = _input_path(source, name)
        if not path.is_file():
            raise ValueError('snapshot_input_not_file')
        with path.open('rb') as stream:
            data = stream.read(10_000_001)
        total += len(data)
        if len(data) > 10_000_000 or total > 100_000_000:
            raise ValueError('snapshot_byte_budget_exceeded')
        files[name] = data
    # Check destination ancestors as well, including junctions on Windows.
    for parent in (destination, *destination.parents):
        if parent.exists() and _linked(parent):
            raise ValueError('linked_snapshot_destination')
    digests = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    for name, expected in digests.items():
        if hashlib.sha256(_input_path(source, name).read_bytes()).hexdigest() != expected:
            raise ValueError('snapshot_source_changed')
    destination.mkdir(parents=True, exist_ok=False)
    for name, data in files.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return {'schema_version': 'evaluation_input_snapshot.v1', 'file_count': len(files),
            'byte_count': total, 'source_sha256': digests,
            'scope': 'explicit selected files; source left unchanged; no execution or completeness certification'}


def _input_path(root, name):
    if not isinstance(name, str) or not name or '\\' in name or ':' in name:
        raise ValueError('invalid_snapshot_path')
    path = Path(name)
    if (path.is_absolute() or PureWindowsPath(name).drive or '..' in path.parts
            or any(p.lower() in {'.git', '.agents', '.codex', 'config.json', 'secret.key'}
                   or p.lower().startswith('.env') for p in path.parts)):
        raise ValueError('private_or_external_snapshot_path')
    result = root / path
    if not result.resolve().is_relative_to(root):
        raise ValueError('snapshot_path_escape')
    for current in (result, *result.parents):
        if _linked(current):
            raise ValueError('linked_snapshot_input')
    return result


def _linked(path):
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_file_attributes', 0) & 0x400)
