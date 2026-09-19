"""Own description evidence selection and the local explanation contract."""
import json
from pathlib import Path

from .evidence import collect
from .source_lookup import read_requests
from .claim_evidence import review_context
from .review_audit import audit_review
from .single_claim import prepare, validate_result
from .claim_obligations import requirements, validate_obligations
from .lean_claim import validate_lean
from .claim_alignment import validate_aligned
from .description_shape import normalize
from .grounding import claim_grounding
from .return_flags import analyze_requests
from .mechanism_review import validate as validate_mechanism
from .return_property import prepare as prepare_property, validate as validate_property
from .api_contracts import build as api_contract_facts
from .behavior_checks import build as behavior_checks


def run(payload):
    policy = json.loads((Path(__file__).resolve().parents[1] / 'knowledge/description_policy.json').read_text(encoding='utf-8'))
    if policy.get('schema_version') != 'project_description_policy.v1':
        raise ValueError('invalid_description_policy')
    if payload.get('action') == 'behavior_checks':
        facts = behavior_checks(payload['project_root'], payload['evidence'], payload['behavior_checks'], policy['collection'])
        return {'status':'ok','evidence':payload['evidence'],'behavior_facts':facts,
                'instruction':policy['behavior_check_instruction'],'review_instruction':policy['behavior_check_instruction']}
    if payload.get('action') == 'api_contracts':
        facts = api_contract_facts(payload['project_root'], payload['evidence'], payload['requests'], policy['collection'])
        return {'status': 'ok', 'evidence': payload['evidence'], 'api_contract_facts': facts,
                'instruction': policy['api_contract_instruction'], 'review_instruction': policy['api_contract_instruction']}
    if payload.get('action') == 'return_property':
        claim = payload['claims'][0]
        if len(payload['claims']) != 1:
            raise ValueError('return_property_single_claim_required')
        analysis = prepare_property(payload['project_root'], payload['return_property'], claim,
                                    policy['collection'], policy['return_property'])
        result = prepare(payload['evidence'], payload['claims'], policy['single_claim_review'])
        result['coverage_requirements'] = requirements(payload.get('coverage_requirements', policy['coverage_requirements']))
        if 'claim_result' in payload:
            result['claim_validation'] = validate_property(payload['claim_result'], payload['evidence'],
                claim, result['coverage_requirements'], analysis)
        instruction = policy['aligned_claim_instruction'] + '\n' + policy['return_property_instruction']
        if payload['return_property']['kind'] in ('normal_return_for_inputs', 'return_field_equals_for_inputs'):
            instruction += '\n' + policy['api_input_instruction']
        if payload['return_property']['kind'] == 'return_field_equals_for_inputs':
            instruction += '\n' + policy['success_input_instruction']
        return {'status': 'ok', **result, 'return_property_analysis': analysis,
                'instruction': instruction, 'review_instruction': instruction}
    if payload.get('action') == 'return_flags':
        return {'status': 'ok', 'evidence': {},
                'return_flag_analysis': analyze_requests(payload['project_root'], payload['requests'],
                    policy['collection'], policy['return_flags']),
                'coverage_requirements': [policy['return_flags']['coverage_requirement']],
                'instruction': policy['return_flag_instruction'],
                'review_instruction': policy['return_flag_instruction']}
    if payload.get('action') == 'grounding':
        return {'status': 'ok', 'evidence': payload['evidence'],
                'claim_grounding': claim_grounding(payload['description_result'], payload['evidence']),
                'instruction': policy['instruction'], 'review_instruction': policy['review_instruction']}
    if payload.get('action') == 'normalize':
        normalized, receipt = normalize(payload['description_result'], policy['shape_normalization'])
        return {'status': 'ok', 'evidence': payload['evidence'],
                'normalized_description': normalized, 'shape_receipt': receipt,
                'instruction': policy['instruction'], 'review_instruction': policy['review_instruction']}
    if payload.get('action') in ('claim_review', 'claim_review_v2', 'claim_review_v3', 'claim_review_v4', 'mechanism_review'):
        result = prepare(payload['evidence'], payload['claims'], policy['single_claim_review'])
        structured = payload['action'] != 'claim_review'
        if structured:
            result['coverage_requirements'] = requirements(payload.get('coverage_requirements',
                                                                       policy['coverage_requirements']))
        if 'claim_result' in payload:
            validator = {'claim_review_v3': validate_lean, 'claim_review_v4': validate_aligned}.get(
                payload['action'], validate_obligations)
            result['claim_validation'] = (validate_mechanism(payload['claim_result'], payload['evidence'],
                payload['claims'][0], result['coverage_requirements'], payload['return_flag_analysis'])
                if payload['action'] == 'mechanism_review' else validator(payload['claim_result'], payload['evidence'],
                payload['claims'][0], result['coverage_requirements']) if structured else
                validate_result(payload['claim_result'], payload['evidence']))
        instruction = policy[{'claim_review': 'claim_instruction', 'claim_review_v2': 'obligation_instruction',
                              'claim_review_v3': 'lean_claim_instruction',
                              'claim_review_v4': 'aligned_claim_instruction',
                              'mechanism_review': 'mechanism_instruction'}[payload['action']]]
        return {'status': 'ok', **result, 'instruction': instruction, 'review_instruction': instruction}
    if payload.get('action') == 'review':
        result = review_context(payload['evidence'], payload['claims'], policy['claim_review'])
        if 'reviews' in payload:
            result['review_audit'] = audit_review(payload['evidence'], payload['claims'], payload['reviews'],
                                                  visible_evidence=payload.get('review_evidence'))
        return {'status': 'ok', **result, 'instruction': policy['instruction'],
                'review_instruction': policy['review_instruction']}
    evidence = ({'sources': read_requests(payload['project_root'], payload['requests'], policy['collection'])}
                if payload.get('action') == 'read' else collect(payload['project_root'], policy['collection']))
    return {'status': 'ok', 'evidence': evidence,
            'instruction': policy['instruction'], 'review_instruction': policy['review_instruction']}
