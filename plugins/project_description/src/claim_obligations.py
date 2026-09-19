"""Aggregate declared obligations; source quotes are not semantic proof."""
from copy import deepcopy

from .single_claim import validate_result


def requirements(value):
    if not isinstance(value, list) or not 1 <= len(value) <= 6:
        raise ValueError('claim_coverage_requirements_required')
    seen = set()
    for row in value:
        if (not isinstance(row, dict) or set(row) != {'id', 'description'}
                or not isinstance(row['id'], str) or not row['id'].strip() or not 1 <= len(row['id']) <= 80
                or row['id'] in seen or not isinstance(row['description'], str)
                or not row['description'].strip() or len(row['description']) > 500):
            raise ValueError('claim_invalid_coverage_requirement')
        seen.add(row['id'])
    return deepcopy(value)


def _assessment(verdict, reason, citations, evidence):
    validate_result({'verdict': verdict, 'reason': reason, 'citations': citations,
                     'proposed_text': None}, evidence)


def validate_obligations(response, evidence, claim, required):
    """Check complete textual coverage and derive a conservative overall verdict."""
    required = requirements(required)
    base = {'verdict', 'reason', 'citations', 'proposed_text'}
    if not isinstance(response, dict) or set(response) != base | {'parts', 'coverage'}:
        raise ValueError('claim_obligations_invalid_result')
    validate_result({key: response[key] for key in base}, evidence)
    parts = response['parts']
    if not isinstance(parts, list) or not 1 <= len(parts) <= 8:
        raise ValueError('claim_parts_required')
    text, effective, reasons = '', [], []
    for part in parts:
        if (not isinstance(part, dict)
                or set(part) != {'text', 'verdict', 'reason', 'citations', 'counterexamples'}
                or not isinstance(part['text'], str) or not part['text'].strip()):
            raise ValueError('claim_invalid_part')
        text += part['text']
        _assessment(part['verdict'], part['reason'], part['citations'], evidence)
        # A reported counterexample must quote visible code. Its relevance still
        # requires semantic review; never infer it merely from a lexical match.
        _assessment('uncertain', 'Counterexample quotations', part['counterexamples'], evidence)
        verdict = 'refuted' if part['counterexamples'] else part['verdict']
        effective.append(verdict)
        if part['counterexamples']:
            reasons.append('declared_counterexample')
    if text != claim['text']:
        raise ValueError('claim_parts_do_not_cover_original_text')
    coverage = response['coverage']
    if not isinstance(coverage, list) or len(coverage) != len(required):
        raise ValueError('claim_incomplete_coverage_review')
    ids = []
    for row in coverage:
        if (not isinstance(row, dict) or set(row) != {'id', 'status', 'reason', 'citations'}
                or not isinstance(row['id'], str)
                or row['status'] not in ('shown', 'missing', 'not_applicable')):
            raise ValueError('claim_invalid_coverage_review')
        ids.append(row['id'])
        _assessment('supported' if row['status'] == 'shown' else 'uncertain',
                    row['reason'], row['citations'], evidence)
    if len(set(ids)) != len(ids) or set(ids) != {r['id'] for r in required}:
        raise ValueError('claim_incomplete_coverage_review')
    missing = [row['id'] for row in coverage if row['status'] == 'missing']
    if 'refuted' in effective:
        verdict = 'refuted'
        reasons.append('refuted_part')
    elif response['verdict'] == 'refuted':
        raise ValueError('claim_global_refutation_without_refuted_part')
    elif 'uncertain' in effective or missing or response['verdict'] == 'uncertain':
        verdict = 'uncertain'
        reasons.append('uncertain_assessment_or_missing_context')
    else:
        verdict = 'supported'
    result = deepcopy(response)
    result['model_verdict'] = result['verdict']
    result['verdict'] = verdict
    return {'quote_validation': 'passed', 'semantic_verified': False,
            'execution_authorized': False, 'normalized_result': result,
            'aggregation': {'part_verdicts': effective, 'missing_context': missing,
                            'reasons': sorted(set(reasons)),
                            'model_verdict_overridden': verdict != response['verdict'],
                            'text_coverage': 'complete', 'semantic_decomposition': 'unverified'}}
