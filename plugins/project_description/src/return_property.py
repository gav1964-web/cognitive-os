"""Bind a reviewer-specified claim property before consulting model opinions."""
from copy import deepcopy
import hashlib
import json

from .claim_alignment import validate_aligned
from .helper_context import sections
from .return_paths import analyze
from .api_inputs import analyze_inputs
from .source_lookup import read_requests


def prepare(root, property, claim, collection, policy):
    success = isinstance(property, dict) and property.get('kind') == 'return_field_equals_for_inputs'
    invocation = success or (isinstance(property, dict) and property.get('kind') == 'normal_return_for_inputs')
    keys = {'path', 'sha256', 'symbol', 'claim_start', 'claim_end', 'kind', 'inputs' if invocation else 'field'}
    if success:
        keys |= {'field', 'expected'}
    if (not isinstance(property, dict) or set(property) != keys
            or property['kind'] not in ('normal_return_field_true', 'describes_diagnostic', 'normal_return_for_inputs', 'return_field_equals_for_inputs')
            or any(not isinstance(property[k], str) or not property[k] for k in ('path', 'sha256', 'symbol'))
            or not property['symbol'].isidentifier()
            or ((not invocation or success) and (not isinstance(property['field'], str) or not 0 < len(property['field']) <= 100))
            or (success and (type(property['expected']) not in (bool, str, type(None))
                or (isinstance(property['expected'], str) and len(property['expected']) > 100)))
            or (invocation and (not isinstance(property['inputs'], dict) or len(property['inputs']) > 6
                or any(not isinstance(k, str) or not k.isidentifier() or type(v) not in (bool, type(None))
                       for k, v in property['inputs'].items())))
            or any(type(property[k]) is not int for k in ('claim_start', 'claim_end'))
            or not 0 <= property['claim_start'] < property['claim_end'] <= len(claim['text'])):
        raise ValueError('invalid_return_property')
    source = read_requests(root, [{k: property[k] for k in ('path', 'sha256', 'symbol')}], collection)[0]
    spans = sections(source['excerpt'])
    callers = [s for s in spans if s['name'] == property['symbol']]
    if (len(callers) != 1 or not callers[0]['complete']
            or source.get('helper_context', {}).get('caller_truncated', True)
            or any(not s['complete'] for s in spans)):
        result = {'status': 'unknown', 'complete': False, 'reason': 'complete_function_context_required',
                  'source_executed': False, 'semantic_verified': False}
    else:
        text = '\n\n'.join(s['text'].split('\n', 1)[1] for s in spans)
        condition = {k: property[k] for k in ('field', 'expected')} if success else None
        result = (analyze_inputs(text, property['symbol'], property['inputs'], success=condition) if invocation else
                  analyze(text, property['symbol'], property['field'], max_inputs=policy['max_inputs'],
                          max_cases=policy['max_cases']))
    if len(json.dumps(result, ensure_ascii=False)) > policy['max_analysis_characters']:
        result = {'status': 'unknown', 'complete': False, 'reason': 'analysis_character_budget',
                  'source_executed': False, 'semantic_verified': False}
    receipt = {'schema_version': 'claim_return_property.v1', 'property': deepcopy(property),
               'claim_fragment': claim['text'][property['claim_start']:property['claim_end']],
               'authority': 'explicit_reviewer_binding_not_model_selected', 'analysis': result,
               'execution_authorized': False, 'semantic_verified': False,
               'binding_limit': ('The reviewer must establish that this returned field/value represents successful behavior for these inputs.' if success else
                                'The reviewer must establish that normal return for these inputs represents the natural-language claim.'
                                 if invocation else 'The reviewer must establish that this field/property represents the natural-language claim.')}
    receipt['digest'] = hashlib.sha256(json.dumps(receipt, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return receipt


def validate(response, evidence, claim, required, receipt):
    original = validate_aligned(response, evidence, claim, required)
    projected = deepcopy(response)
    property, analysis = receipt['property'], receipt['analysis']
    findings, offset = [], 0
    for index, part in enumerate(original['normalized_result']['parts']):
        start, end = offset, offset + len(part['text'])
        offset = end
        overlap = start < property['claim_end'] and end > property['claim_start']
        if (overlap and property['kind'] in ('normal_return_field_true', 'normal_return_for_inputs', 'return_field_equals_for_inputs')
                and analysis['status'] != 'holds_in_model'):
            downgraded = part['verdict'] == 'supported'
            findings.append({'part_index': index, 'analysis_status': analysis['status'],
                             'downgraded': downgraded, 'model_verdict': part['verdict']})
            if downgraded:
                projected['parts'][index]['verdict'] = 'uncertain'
                label = ('Explicit returned-field criterion' if property['kind'] == 'return_field_equals_for_inputs'
                         else 'Explicit normal-return property')
                projected['parts'][index]['reason'] = label + ' not established: ' + analysis['status']
    result = validate_aligned(projected, evidence, claim, required)
    result['return_property_audit'] = {
        'schema_version': 'claim_return_property_audit.v1', 'property_digest': receipt['digest'],
        'authority': 'reviewer_selected_property_under_declared_model_assumptions',
        'findings': findings, 'original_part_verdicts': [p['verdict'] for p in original['normalized_result']['parts']],
        'analysis_status': analysis['status'], 'semantic_verified': False,
        'limits': [receipt['binding_limit'], 'Model proof covers Boolean/None inputs and owned dicts only.',
                   'Unknown analysis is not a refutation; diagnostic descriptions are not guarantees.'],
    }
    if property['kind'] == 'normal_return_for_inputs':
        result['return_property_audit']['limits'].append(
            'Explicit keyword invocation checks normal return, not useful output or arbitrary input support.')
    if property['kind'] == 'return_field_equals_for_inputs':
        result['return_property_audit']['limits'].append(
            'A returned field/value is an explicit success criterion, not independent proof of successful external effects.')
    result['aggregation']['origin'] = 'parts_coverage_and_explicit_return_property'
    result['aggregation']['model_verdict_overridden'] = any(f['downgraded'] for f in findings)
    return result
