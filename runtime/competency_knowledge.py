"""Versioned, read-only knowledge contributions from registered competencies."""
from __future__ import annotations

import inspect
import hashlib
import json
from pathlib import Path

from .plugin_loader import load_capability, load_entrypoint
from .schema import validate_payload
from .integrity import implementation_files

ROOT = Path(__file__).resolve().parents[1]
_IMPORTED_CODE: dict[str, str] = {}


def providers(root: Path = ROOT) -> list[dict]:
    path = root / 'config/knowledge_providers.json'
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('schema_version') != 'knowledge_providers.v1':
        raise ValueError('invalid_knowledge_provider_catalog')
    rows = data.get('providers')
    if not isinstance(rows, list):
        raise ValueError('invalid_knowledge_providers')
    owners, ids = set(), set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('capability'), str):
            raise ValueError('invalid_knowledge_provider')
        if row['capability'] in ids:
            raise ValueError('duplicate_knowledge_provider')
        ids.add(row['capability'])
        for field in ('catalogs', 'profile_ids'):
            if not isinstance(row.get(field), list) or any(not isinstance(x, str) or not x for x in row[field]):
                raise ValueError('invalid_knowledge_provider_metadata')
        for name in row['profile_ids']:
            if name in owners:
                raise ValueError('ambiguous_knowledge_owner')
            owners.add(name)
    return rows


def invoke_knowledge(capability_id: str, payload: dict, *, root: Path = ROOT) -> dict:
    """Validate current code+KB identity and schemas; no persistent result cache."""
    root = root.resolve()
    capability = load_capability(root, capability_id)
    records = json.loads((root / 'registry/capabilities.json').read_text(encoding='utf-8'))
    matches = [row for row in records['capabilities'] if row['id'] == capability_id]
    if len(matches) != 1 or matches[0].get('version_hash') != capability.version_hash:
        raise ValueError('knowledge_provider_identity_mismatch')
    if capability.lifecycle_status != 'active' or matches[0].get('lifecycle_status') != 'active':
        raise ValueError('knowledge_provider_not_active')
    if (capability.side_effects.get('filesystem') not in {'none', 'read_only'}
            or capability.side_effects.get('network') != 'none'
            or capability.side_effects.get('secrets') != 'none'):
        raise ValueError('knowledge_provider_effects_not_read_only')
    validate_payload(payload, capability.input_schema, label=f'{capability_id}.input')
    code = hashlib.sha256()
    for path in sorted((root / 'plugins' / capability_id / 'src').rglob('*.py')):
        code.update(path.relative_to(root).as_posix().encode() + b'\0' + path.read_bytes())
    code_digest = code.hexdigest()
    identities = {capability.entrypoint: code_digest}
    implementations = {}
    for label, path in implementation_files(root / 'plugins' / capability_id):
        package = '/'.join(label.split('/')[:2])
        implementations.setdefault(package, hashlib.sha256()).update(label.encode() + b'\0' + path.read_bytes())
    identities.update({name: digest.hexdigest() for name, digest in implementations.items()})
    if any(name in _IMPORTED_CODE and _IMPORTED_CODE[name] != digest for name, digest in identities.items()):
        raise ValueError('knowledge_provider_code_changed_restart_required')
    function = load_entrypoint(capability.entrypoint)
    origin = inspect.getsourcefile(function)
    if not origin or not Path(origin).resolve().is_relative_to(root / 'plugins' / capability_id):
        raise ValueError('knowledge_provider_import_origin_mismatch')
    _IMPORTED_CODE.update(identities)
    result = function(payload)
    validate_payload(result, capability.output_schema, label=f'{capability_id}.output')
    if load_capability(root, capability_id).version_hash != capability.version_hash:
        raise ValueError('knowledge_provider_changed_during_call')
    return result


def catalog_records(catalog: str, *, root: Path = ROOT) -> list[dict]:
    records = []
    for provider in providers(root):
        if catalog not in provider['catalogs']:
            continue
        result = invoke_knowledge(provider['capability'], {'operation': catalog}, root=root)
        contribution = result.get('records')
        if result.get('status') != 'ok' or not isinstance(contribution, list):
            raise ValueError('invalid_knowledge_contribution')
        if any(not isinstance(row, dict) for row in contribution):
            raise ValueError('invalid_knowledge_record')
        if catalog == 'boundary_profiles' and any(row.get('id') not in provider['profile_ids'] for row in contribution):
            raise ValueError('knowledge_profile_owner_mismatch')
        records.extend(contribution)
    return records


def decorate_profile(profile: dict, *, root: Path = ROOT) -> dict:
    owner = next((row for row in providers(root) if profile.get('id') in row['profile_ids']), None)
    if owner is None:
        return profile
    result = invoke_knowledge(owner['capability'], {'operation': 'decorate_profile', 'profile': profile}, root=root)
    decorated = result.get('profile')
    if result.get('status') != 'ok' or not isinstance(decorated, dict) or decorated.get('id') != profile.get('id'):
        raise ValueError('invalid_decorated_profile')
    return decorated
