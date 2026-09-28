"""Check consistency of model-declared claim bindings, never infer semantic truth."""
from copy import deepcopy

from .claim_alignment import validate_aligned


def _row(row, index, functions):
    keys = {'part_index', 'subject', 'scope', 'intent', 'basis', 'bindings', 'reason'}
    if (not isinstance(row, dict) or set(row) != keys
            or type(row['part_index']) is not int or row['part_index'] != index
            or row['intent'] not in ('enforces', 'reports', 'other', 'unknown')
            or row['scope'] not in ('suffix_return', 'normal_return', 'whole_operation', 'not_applicable', 'unknown')
            or row['basis'] not in ('suffix', 'other_code', 'not_applicable', 'unknown')
            or any(not isinstance(row[k], str) or not row[k].strip() or len(row[k]) > 600
                   for k in ('subject', 'reason'))
            or not isinstance(row['bindings'], list) or len(row['bindings']) > 6):
        raise ValueError('mechanism_invalid_part_binding')
    selected, seen = [], set()
    for binding in row['bindings']:
        if (not isinstance(binding, dict) or set(binding) != {'path', 'symbol', 'field'}
                or any(not isinstance(v, str) for v in binding.values())):
            raise ValueError('mechanism_invalid_field_binding')
        key = tuple(binding[k] for k in ('path', 'symbol', 'field'))
        if key in seen or key not in functions:
            raise ValueError('mechanism_unknown_or_duplicate_field')
        seen.add(key)
        selected.append(functions[key])
    return selected


def validate(response, evidence, claim, required, analysis):
    if not isinstance(response, dict) or 'mechanisms' not in response:
        raise ValueError('mechanism_bindings_required')
    projected = {k: deepcopy(v) for k, v in response.items() if k != 'mechanisms'}
    original = validate_aligned(projected, evidence, claim, required)
    parts = original['normalized_result']['parts']
    rows = response['mechanisms']
    if not isinstance(rows, list) or len(rows) != len(parts):
        raise ValueError('mechanism_incomplete_part_bindings')
    fields = {}
    for function in analysis['functions']:
        for field in function.get('model', {}).get('fields', []):
            fields[(function['path'], function['symbol'], field['field'])] = field
    findings = []
    for index, (part, row) in enumerate(zip(parts, rows)):
        selected = _row(row, index, fields)
        reasons = []
        if row['intent'] == 'unknown':
            reasons.append('claim_intent_unresolved')
        if row['intent'] == 'enforces':
            if row['scope'] in ('unknown', 'not_applicable'):
                reasons.append('guarantee_scope_unresolved')
            if row['basis'] in ('unknown', 'not_applicable'):
                reasons.append('enforcement_basis_unresolved')
            if row['basis'] == 'suffix':
                if not selected:
                    reasons.append('no_predicate_binding')
                if any(f['false_return_witness'] is not None for f in selected):
                    reasons.append('suffix_allows_false_return')
                if row['scope'] != 'suffix_return':
                    reasons.append('suffix_does_not_cover_whole_function')
                if any(not f['all_normal_returns_true_in_model'] for f in selected):
                    reasons.append('suffix_has_no_established_true_postcondition')
        if row['basis'] == 'suffix' and not selected and 'no_predicate_binding' not in reasons:
            reasons.append('no_predicate_binding')
        if reasons:
            changed = part['verdict'] == 'supported'
            findings.append({'part_index': index, 'codes': reasons,
                             'model_verdict': part['verdict'], 'downgraded': changed})
            if changed:
                projected['parts'][index]['verdict'] = 'uncertain'
                projected['parts'][index]['reason'] = 'Consistency guard: ' + ', '.join(reasons)
    result = validate_aligned(projected, evidence, claim, required)
    result['mechanism_audit'] = {
        'schema_version': 'claim_mechanism_audit.v1',
        'authority': 'consistency_of_model_bindings_not_semantic_certification',
        'bindings': deepcopy(rows), 'findings': findings,
        'original_aggregate': original['normalized_result']['verdict'],
        'original_part_verdicts': [p['verdict'] for p in parts],
        'semantic_verified': False, 'full_function_reachability_proven': False,
        'limits': ['Model can misclassify a guarantee as reporting or bind the wrong predicate.',
                   'Other-code enforcement remains a cited model opinion, not a verified proof.',
                   'Conditional suffix witnesses are not executed project counterexamples.'],
    }
    result['aggregation']['origin'] = 'parts_coverage_and_mechanism_consistency'
    result['aggregation']['model_verdict_overridden'] = any(f['downgraded'] for f in findings)
    return result
