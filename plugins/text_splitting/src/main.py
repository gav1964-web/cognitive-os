"""Registered text helper proposals and local recipe; no source application."""
import json
from pathlib import Path

from .extractor import _extract_splitlines_helper

KNOWLEDGE = Path(__file__).resolve().parents[1] / 'knowledge'


def run(payload: dict) -> dict:
    operation = payload['operation']
    if operation == 'patch_recipes':
        document = json.loads((KNOWLEDGE / 'patch_recipes.json').read_text(encoding='utf-8'))
        if document.get('schema_version') != 'text_splitting_recipes.v1':
            raise ValueError('invalid_text_splitting_recipes_schema')
        return {'status':'ok', 'records':document['recipes']}
    if operation not in {'propose_patch', 'propose_helper'}:
        raise ValueError('unsupported_text_splitting_operation')
    patch = _extract_splitlines_helper(
        payload['source'], origin_symbol=payload['origin_symbol'],
        proposed_symbol=payload['proposed_symbol'],
    )
    if operation == 'propose_patch':
        return {'status':'proposed' if patch is not None else 'not_applicable', 'patch':patch}
    return {'status':'ok', 'proposal':{
        'schema_version':'helper_proposal.v1',
        'status':'proposed' if patch is not None else 'not_applicable',
        'source':patch['source'] if patch is not None else None,
        'operation_details':{key:patch[key] for key in ('text_expression', 'split_line')} if patch is not None else {},
        'reason':None if patch is not None else 'splitlines_helper_pattern_not_proven',
    }}
