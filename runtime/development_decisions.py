"""Small, source-bound engineering decision memory with explicit stale detection."""
from __future__ import annotations

import json
from pathlib import Path

from .source_refactor_analysis import digest
from .stage_finalization_workspace import _atomic_write, owned_path

DECISIONS = 'DEVELOPMENT_DECISIONS.json'


def source_hash(root: Path, name: str) -> str | None:
    path = owned_path(root.resolve(), name)
    if path.name == 'config.json' or path.name.startswith('.env') or any(part in {'.git', '.codex', '.agents'} for part in Path(name).parts):
        raise ValueError('private_path_not_allowed_in_decision_context')
    return digest(path.read_bytes()) if path.is_file() else None


def decision_context(root: Path) -> list[dict]:
    path = owned_path(root.resolve(), DECISIONS)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('schema_version') != 'development_decisions.v1':
        raise ValueError('invalid_decision_memory')
    result = []
    for item in data['decisions']:
        changed = [name for name, expected in item['source_hashes'].items() if source_hash(root, name) != expected]
        result.append({**item, 'status': 'needs_review' if changed else 'current', 'changed_paths': changed})
    return result


def remember_decision(root: Path, *, key: str, decision: str, rationale: str,
                      paths: list[str], reconsider_when: str) -> dict:
    from .development_handoff import _queue_lock, _now
    if not all((key.strip(), decision.strip(), rationale.strip(), paths, reconsider_when.strip())):
        raise ValueError('decision_requires_reason_scope_and_reconsideration_condition')
    root = root.resolve()
    with _queue_lock(root):
        old = decision_context(root)
        item = {'id': key, 'decision': decision, 'rationale': rationale,
                'source_hashes': {name: source_hash(root, name) for name in paths},
                'reconsider_when': reconsider_when, 'recorded_at': _now()}
        if any(value is None for value in item['source_hashes'].values()):
            raise ValueError('decision_source_missing')
        kept = [{k: v for k, v in row.items() if k not in {'status', 'changed_paths'}} for row in old if row['id'] != key]
        data = {'schema_version': 'development_decisions.v1', 'decisions': [*kept, item]}
        _atomic_write(owned_path(root, DECISIONS), (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
        return item
