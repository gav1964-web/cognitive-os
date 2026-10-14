"""V3: quote evidence once and derive the overall verdict in code."""
from copy import deepcopy

from .claim_obligations import requirements
from .single_claim import validate_result


def _check(verdict, reason, citations, evidence):
    validate_result({'verdict': verdict, 'reason': reason, 'citations': citations,
                     'proposed_text': None}, evidence)


def validate_lean(response, evidence, claim, required):
    required = requirements(required)
    if (not isinstance(response, dict) or set(response) - {'parts', 'coverage', 'proposed_text'}
            or not {'parts', 'coverage'} <= set(response)):
        raise ValueError('claim_v3_invalid_result')
    proposed = response.get('proposed_text')
    validate_result({'verdict': 'uncertain', 'reason': 'Proposal syntax',
                     'citations': [], 'proposed_text': proposed}, evidence)
    parts = response['parts']
    if not isinstance(parts, list) or not 1 <= len(parts) <= 8:
        raise ValueError('claim_parts_required')
    quotes, text, verdicts = [], '', []
    for part in parts:
        if (not isinstance(part, dict) or set(part) != {'text', 'verdict', 'reason', 'citations'}
                or not isinstance(part['text'], str) or not part['text'].strip()):
            raise ValueError('claim_v3_invalid_part')
        _check(part['verdict'], part['reason'], part['citations'], evidence)
        text += part['text']
        verdicts.append(part['verdict'])
        quotes.extend(part['citations'])
    if text != claim['text']:
        raise ValueError('claim_parts_do_not_cover_original_text')
    coverage = response['coverage']
    if not isinstance(coverage, dict) or set(coverage) != {row['id'] for row in required}:
        raise ValueError('claim_v3_incomplete_coverage')
    rows, missing, contradicted = [], [], []
    for requirement in required:
        key = requirement['id']
        row = coverage[key]
        if (not isinstance(row, dict) or set(row) != {'status', 'reason', 'citations'}
                or row['status'] not in ('shown', 'contradicted', 'missing', 'not_applicable')):
            raise ValueError('claim_v3_invalid_coverage')
        _check('supported' if row['status'] in ('shown', 'contradicted') else 'uncertain',
               row['reason'], row['citations'], evidence)
        rows.append({'id': key, **deepcopy(row)})
        quotes.extend(row['citations'])
        if row['status'] == 'missing':
            missing.append(key)
        elif row['status'] == 'contradicted':
            contradicted.append(key)
    if 'refuted' in verdicts or contradicted:
        verdict, reason = 'refuted', 'Есть опровергнутая часть или связь.'
    elif 'uncertain' in verdicts or missing:
        verdict, reason = 'uncertain', 'Есть неопределённая часть или недостающий контекст.'
    else:
        verdict, reason = 'supported', 'Все заявленные части подтверждены оценками, пробелов контекста не отмечено.'
    unique = []
    for quote in quotes:
        if quote not in unique:
            unique.append(deepcopy(quote))
    result = {'verdict': verdict, 'reason': reason, 'model_verdict': None, 'citations': unique,
              'proposed_text': proposed, 'parts': deepcopy(parts), 'coverage': rows}
    return {'quote_validation': 'passed', 'semantic_verified': False, 'execution_authorized': False,
            'normalized_result': result, 'aggregation': {
                'origin': 'derived_from_parts_and_coverage', 'part_verdicts': verdicts,
                'missing_context': missing, 'contradicted_context': contradicted,
                'model_verdict_overridden': False, 'text_coverage': 'complete',
                'semantic_decomposition': 'unverified'}}
