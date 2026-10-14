"""Explicit coverage of source assertions; never claims their execution outcome."""
import ast
import hashlib
import json
import textwrap
from copy import deepcopy

from .narrow_type_evidence_binding import content_digest
from .project_failure_prompt_context import test_source_groups

GROUNDING_FIELDS = ('branch_digest', 'reached_return_ids', 'reached_returns',
                    'assertion_contract', 'assertion_plan', 'proposal_route', 'request_context_digest',
                    'preservation_evidence', 'preservation_plan')


def repair_grounding(design):
    return {k: deepcopy(design[k]) for k in GROUNDING_FIELDS if k in design}


def build_assertion_contract(packet):
    rows = []
    for group in test_source_groups(packet.get('test_sources') or []):
        excerpt = group.get('excerpt', '')
        if (group.get('excerpt_complete') is not True or not group.get('file_sha256')
                or hashlib.sha256(excerpt.encode('utf-8')).hexdigest() != group.get('sha256')):
            raise ValueError('complete_source_bound_assertions_required')
        tree = ast.parse(textwrap.dedent(excerpt))
        if len(tree.body) != 1 or not isinstance(tree.body[0], (ast.FunctionDef, ast.AsyncFunctionDef)):
            raise ValueError('single_test_function_required')
        function = tree.body[0]
        assertions = [n for n in function.body if isinstance(n, ast.Assert)]
        if not assertions or len(assertions) != sum(isinstance(n, ast.Assert) for n in ast.walk(function)):
            raise ValueError('only_direct_test_assertions_supported')
        for node in assertions:
            rows.append({'id': f'A{len(rows) + 1:03d}', 'nodeids': group['nodeids'],
                'path': group['path'], 'file_sha256': group['file_sha256'], 'excerpt_sha256': group['sha256'],
                'excerpt_line': node.lineno, 'assertion': ast.get_source_segment(textwrap.dedent(excerpt), node)})
    if not 1 <= len(rows) <= 64 or len(json.dumps(rows)) > 12000:
        raise ValueError('assertion_contract_budget_exceeded')
    result = {'schema_version': 'repair_assertion_contract.v1', 'packet_digest': packet['packet_digest'],
        'assertions': rows, 'execution_authorized': False,
        'scope': 'All direct assertions in supplied complete test excerpts, not all project tests. '
            'Declared source obligations only; baseline reachability and individual outcomes are not inferred.'}
    result['contract_digest'] = content_digest(result)
    return result


def assertion_plan_schema(contract):
    return {'type': 'array', 'minItems': len(contract['assertions']), 'maxItems': len(contract['assertions']),
        'items': {'type': 'object', 'additionalProperties': False, 'required': ['assertion_id', 'behavior'],
            'properties': {'assertion_id': {'type': 'string', 'enum': [r['id'] for r in contract['assertions']]},
                'behavior': {'type': 'string', 'minLength': 12, 'maxLength': 800,
                    'description': 'Explain the behavior this assertion requires and how the design preserves or repairs it.'}}}}


def assertion_prompt_context(contract):
    return {'contract_digest': contract['contract_digest'], 'scope': contract['scope'],
        'assertions': [{k: deepcopy(row[k]) for k in ('id', 'nodeids', 'assertion')}
                       for row in contract['assertions']],
        'projection': 'Repeated file hashes/locations omitted from prompt only; full source-bound contract retained in design.'}


def validate_assertion_plan(contract, plan):
    if (not isinstance(plan, list) or len(plan) != len(contract['assertions'])
            or any(not isinstance(r, dict) or set(r) != {'assertion_id', 'behavior'}
                   or not isinstance(r['behavior'], str) or not 12 <= len(r['behavior'].strip()) <= 800 for r in plan)
            or [r['assertion_id'] for r in plan] != [r['id'] for r in contract['assertions']]):
        raise ValueError('complete_assertion_plan_required')


def validate_assertion_design(packet, design):
    if 'preservation_evidence' in design or 'preservation_plan' in design:
        from .repair_preservation import validate_preservation, validate_preservation_plan
        validate_preservation(packet, design.get('preservation_evidence') or {})
        validate_preservation_plan(design['preservation_evidence'], design.get('preservation_plan'))
    if 'assertion_contract' in design or 'assertion_plan' in design:
        contract = build_assertion_contract(packet)
        if design.get('assertion_contract') != contract:
            raise ValueError('assertion_contract_changed')
        if design.get('proposal_route') == 'direct':
            if not design.get('request_context_digest') or 'assertion_plan' in design:
                raise ValueError('direct_source_obligations_required')
        else:
            validate_assertion_plan(contract, design.get('assertion_plan'))
