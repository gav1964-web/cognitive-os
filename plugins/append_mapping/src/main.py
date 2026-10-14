"""Read-only boundary contribution; registration does not promote staged KB."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from .extractor import _extract_append_mapping_helper
from .proposal import helper_proposal

KNOWLEDGE = Path(__file__).resolve().parents[1] / 'knowledge'


def run(payload: dict) -> dict:
    operation = payload['operation']
    if operation == 'patch_recipes':
        catalog = json.loads((KNOWLEDGE / 'patch_recipes.json').read_text(encoding='utf-8'))
        if catalog.get('schema_version') != 'append_mapping_recipes.v1':
            raise ValueError('invalid_append_mapping_recipes_schema')
        return {'status': 'ok', 'records': catalog['recipes']}
    if operation in {'propose_patch', 'propose_helper'}:
        patch = _extract_append_mapping_helper(
            payload['source'], origin_symbol=payload['origin_symbol'],
            proposed_symbol=payload['proposed_symbol'], maximum_mapping_fields=payload['maximum_mapping_fields'],
        )
        if operation == 'propose_helper':
            return {'status': 'ok', 'proposal': helper_proposal(patch)}
        return {'status': 'proposed' if patch is not None else 'not_applicable', 'patch': patch}
    if operation == 'boundary_profiles':
        catalog = json.loads((KNOWLEDGE / 'project_development_boundary_profiles.json').read_text(encoding='utf-8'))
        return {'status': 'ok', 'records': catalog['profiles']}
    if operation == 'source_contrasts':
        catalog = json.loads((KNOWLEDGE / 'project_development_source_contrasts.json').read_text(encoding='utf-8'))
        return {'status': 'ok', 'records': catalog['contrasts']}
    if operation == 'decorate_profile':
        # This competency has no active overlay; keep all supplied evidence intact.
        return {'status': 'ok', 'profile': deepcopy(payload['profile'])}
    raise ValueError('unsupported_append_mapping_operation')
