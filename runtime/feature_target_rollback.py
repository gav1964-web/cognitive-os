"""Restore an exact COS installation from bound backups; preserve unrelated files.

Receipts are locally trusted operator evidence, not remote authorization.
Default is a read-only plan. A stale target or backup must never be overwritten.
"""
import json
from pathlib import Path

from .feature_acceptance import save
from .feature_workspace import digest, owned_path, verify_selected_source
from .stage_finalization_workspace import _atomic_write


def rollback_target(*, receipt, work, apply=False):
    receipt, work = Path(receipt).resolve(), Path(work).resolve()
    row = json.loads(receipt.read_text(encoding='utf-8'))
    target = Path(row['target']).resolve()
    backup = receipt.parent / 'backup'
    if (row.get('schema_version') != 'feature_target_delivery.v1'
            or row.get('status') != 'installed' or row.get('source_apply') is not True
            or row.get('installation', {}).get('writer') != 'runtime.feature_workspace.install'
            or Path(row['installation']['backup']).resolve() != backup.resolve()
            or work.exists() or work.is_relative_to(target) or target.is_relative_to(work)
            or work.is_relative_to(receipt.parent) or receipt.parent.is_relative_to(work)):
        raise ValueError('feature_rollback_requires_installed_receipt_and_fresh_external_work')
    before, after = row['source_hashes'], row['final_hashes']
    changes = row['installation']['files']
    if (not changes or any(after.get(n) != h for n, h in changes.items())
            or set(after) != set(before) | set(changes)
            or any(after[n] != h for n, h in before.items() if n not in changes)):
        raise ValueError('feature_rollback_inconsistent_inventory')
    verify_selected_source(target, after)
    restore = {}
    current = {}
    for name in changes:
        current[name] = owned_path(target, name).read_bytes()
        data = owned_path(backup, name).read_bytes() if name in before else None
        if data is not None and digest(data) != before[name]:
            raise ValueError('feature_rollback_backup_hash_mismatch')
        restore[name] = data
    result = {'schema_version':'feature_target_rollback.v1','status':'planned',
        'source_apply':False,'target':str(target),'receipt':str(receipt),
        'receipt_sha256':digest(receipt.read_bytes()),'restored_hashes':before,
        'restore':sorted(n for n,v in restore.items() if v is not None),
        'remove':sorted(n for n,v in restore.items() if v is None),
        'scope':'Exact installed files only; no external effects are undone.'}
    work.mkdir(parents=True)
    save(work/'report.json',result)
    if not apply:
        return result
    lock = target/'.cos-feature.lock'
    with lock.open('x'):
        pass
    written = []
    try:
        if digest(receipt.read_bytes()) != result['receipt_sha256']:
            raise ValueError('feature_rollback_receipt_changed')
        verify_selected_source(target, after)
        for name,data in restore.items():
            if data is not None and owned_path(backup,name).read_bytes() != data:
                raise ValueError('feature_rollback_backup_changed')
        for name,data in restore.items():
            path = owned_path(target,name)
            written.append(name)
            if data is None:
                path.unlink()
            else:
                _atomic_write(path,data)
        verify_selected_source(target,before)
        if any(owned_path(target,n).exists() for n in result['remove']):
            raise ValueError('feature_rollback_new_file_remains')
    except BaseException:
        for name in reversed(written):
            _atomic_write(owned_path(target,name),current[name])
        raise
    finally:
        lock.unlink()
    result.update(status='rolled_back',source_apply=True)
    save(work/'report.json',result)
    return result
