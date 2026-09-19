"""Compact repeated test evidence without losing native node identities."""
from copy import deepcopy


def test_source_groups(rows: list[dict]) -> list[dict]:
    groups = {}
    for row in rows:
        # Bind grouping to actual text and hashes, not just a shared test path.
        key = (row.get('path'), row.get('sha256'), row.get('file_sha256'), row.get('excerpt'))
        if key not in groups:
            groups[key] = {name: deepcopy(value) for name, value in row.items() if name != 'nodeid'}
            groups[key]['nodeids'] = []
        if row.get('nodeid') not in groups[key]['nodeids']:
            groups[key]['nodeids'].append(row.get('nodeid'))
    return list(groups.values())


def hypothesis_response_schema(envelope: dict) -> dict:
    schema = {'type': 'object', 'additionalProperties': False,
        'required': ['target', 'failure_signature', 'mechanism', 'repair_mechanism',
            'mutation_contract', 'residual_risks', 'confidence'],
        'properties': {
            'target': {'type': 'string', 'const': envelope['target']},
            'failure_signature': {'type': 'string', 'const': envelope['failure_signature']},
            'mechanism': {'type': 'string', 'minLength': 24,
                'description': 'Specific causal explanation accounting for all supplied failures.'},
            'repair_mechanism': {'type': 'string', 'minLength': 24,
                'description': 'Abstract behavior change without code or patch text.'},
            'mutation_contract': {'type': 'object', 'additionalProperties': False,
                'required': ['precondition', 'change', 'preserved_behavior'],
                'properties': {key: {'type': 'string', 'minLength': 12} for key in
                    ['precondition', 'change', 'preserved_behavior']}},
            'residual_risks': {'type': 'array', 'minItems': 1,
                'items': {'type': 'string', 'minLength': 1}},
            'confidence': {'type': 'number', 'minimum': 0, 'maximum': 1,
                'description': 'Your assessed confidence in the diagnosis; no default value. Express uncertainty honestly.'}}}
    if envelope.get('edit_scope'):
        schema['required'].append('related_targets')
        schema['properties']['related_targets']={'type':'array','maxItems':2,'uniqueItems':True,
            'items':{'type':'string','enum':envelope['edit_scope']['eligible_related_targets']},
            'description':'Select existing sibling methods when a coherent repair needs their behavior to change too; otherwise empty. Explain their changes in repair_mechanism and preservation contract.'}
    return schema


def candidate_response_schema() -> dict:
    return {'type':'object','additionalProperties':False,'required':['candidates'],
        'properties':{'candidates':{'type':'array','minItems':1,'maxItems':4,
            'items':{'type':'object','additionalProperties':False,
                'required':['id','replacement_source','reason'],
                'properties':{
                    'id':{'type':'string','minLength':1,'maxLength':64},
                    'replacement_source':{'type':'string','minLength':1,'maxLength':8000,
                        'description':'Exactly one complete target function, unchanged signature and annotation. Imports belong inside its body.'},
                    'reason':{'type':'string','minLength':1,'maxLength':1200}}}}}}
