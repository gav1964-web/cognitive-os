"""Prepare a source-bound review job; execution is one explicitly invoked request."""
from copy import deepcopy
from dataclasses import replace
import json

from .competency_knowledge import ROOT, invoke_knowledge
from .narrow_type_evidence_binding import content_digest
from .project_description import _sources_current, description_model_config
from .description_claim_namespace import report_claims
from .local_inference import LocalInferenceError, call_json_chat

_UNSET = object()

def prepare_claim_review(report, claim_id, *, requests=None, root=ROOT, review_version=4,
                         coverage_requirements=None, claim_namespace='draft', return_flags=None,
                         mechanism_review=False, return_property=None):
    if type(review_version) is not int or review_version not in (1, 2, 3, 4):
        raise ValueError('claim_review_invalid_version')
    if review_version == 1 and coverage_requirements is not None:
        raise ValueError('claim_coverage_requires_v2')
    if claim_namespace == 'final' and review_version != 4:
        raise ValueError('claim_review_final_requires_v4')
    if return_flags is not None and review_version != 4:
        raise ValueError('return_flag_requires_v4')
    if type(mechanism_review) is not bool or (mechanism_review and (review_version != 4 or return_flags is None)):
        raise ValueError('mechanism_requires_v4_return_flags')
    if return_property is not None and (review_version != 4 or mechanism_review or return_flags is not None):
        raise ValueError('return_property_requires_separate_v4_job')
    evidence = report['evidence']
    if not _sources_current(evidence):
        raise ValueError('claim_review_stale_sources')
    claim = next((row for row in report_claims(report, claim_namespace, root=root) if row['id'] == claim_id), None)
    if claim is None:
        raise ValueError('claim_review_unknown_claim')
    if requests is not None:
        catalog = {row['path']: row['sha256'] for row in evidence.get('source_catalog', [])}
        catalog.update({row['path']: row['sha256'] for row in evidence['sources']})
        bound = []
        for row in requests:
            if (not isinstance(row, dict) or set(row) - {'path', 'symbol', 'start_line', 'end_line'}
                    or not isinstance(row.get('path'), str) or row['path'] not in catalog):
                raise ValueError('claim_review_unknown_lookup')
            bound.append({**row, 'sha256': catalog[row['path']]})
        selected = invoke_knowledge('project_description', {'project_root': evidence['root'],
            'action': 'read', 'requests': bound}, root=root)['evidence']['sources']
    else:
        selected = [row for row in evidence['sources'] if row['id'] in claim['evidence_ids']]
    focused = {'root': evidence['root'], 'sources': selected}
    item = {**claim, 'evidence_ids': [row['id'] for row in selected]}
    extra = {'coverage_requirements': coverage_requirements} if coverage_requirements is not None else {}
    contribution = invoke_knowledge('project_description', {'project_root': evidence['root'],
        'action': f'claim_review_v{review_version}' if review_version > 1 else 'claim_review',
        'evidence': focused, 'claims': [item], **extra}, root=root)
    job = {'schema_version': f'single_claim_review_job.v{review_version}', 'source_report_digest': content_digest(report),
           'claim_namespace': claim_namespace, 'original_claim': deepcopy(claim), 'claim': item,
           'evidence': contribution['evidence'], 'instruction': contribution['instruction'],
           'claim_packets': contribution['claim_packets'], 'execution_authorized': False}
    if review_version > 1:
        job['coverage_requirements'] = contribution['coverage_requirements']
    if return_flags is not None:
        from .description_return_flags import prepare_flags
        bound, analysis, instruction, requirement = prepare_flags(return_flags, job['evidence'], root=root)
        if any(r['id'] == requirement['id'] for r in job['coverage_requirements']):
            raise ValueError('return_flag_reserved_coverage')
        job['return_flag_requests'] = bound
        job['return_flag_analysis'] = analysis
        job['coverage_requirements'] = [*job['coverage_requirements'], requirement]
        job['instruction'] += '\n' + instruction
    if mechanism_review:
        job['mechanism_contract'] = 'claim_mechanism.v1'
        job['instruction'] = _mechanism_contribution(job, root=root)['instruction']
    if return_property is not None:
        from .description_return_property import bind
        bind(job, return_property, root=root)
    job['digest'] = content_digest(job)
    checked_job(job, root=root)
    return job


def _mechanism_contribution(job, *, root=ROOT, response=_UNSET):
    payload = {'project_root': job['evidence']['root'], 'action': 'mechanism_review',
               'evidence': job['evidence'], 'claims': [job['claim']],
               'coverage_requirements': job['coverage_requirements'],
               'return_flag_analysis': job['return_flag_analysis']}
    if response is not _UNSET:
        payload['claim_result'] = response
    return invoke_knowledge('project_description', payload, root=root)


def checked_job(job, *, root=ROOT):
    if (not isinstance(job, dict)
            or job.get('schema_version') not in tuple(f'single_claim_review_job.v{v}' for v in (1, 2, 3, 4))
            or job.get('execution_authorized') is not False
            or job.get('claim_namespace') not in ('draft', 'final')
            or (job.get('claim_namespace') == 'final' and job.get('schema_version') != 'single_claim_review_job.v4')
            or job.get('digest') != content_digest({k: v for k, v in job.items() if k != 'digest'})):
        raise ValueError('invalid_claim_review_job')
    if not _sources_current(job['evidence']):
        raise ValueError('claim_review_stale_sources')
    from .description_return_flags import check_flags
    check_flags(job, root=root)
    from .description_return_property import check
    check(job, root=root)
    if 'mechanism_contract' in job:
        if (job['mechanism_contract'] != 'claim_mechanism.v1'
                or job['schema_version'] != 'single_claim_review_job.v4'
                or 'return_flag_analysis' not in job):
            raise ValueError('invalid_mechanism_contract')
        if job['instruction'] != _mechanism_contribution(job, root=root)['instruction']:
            raise ValueError('mechanism_instruction_changed')
    if not job['schema_version'].endswith('.v1'):
        if (job.get('claim', {}).get('text') != job.get('original_claim', {}).get('text')
                or job.get('claim', {}).get('id') != job.get('original_claim', {}).get('id')
                or 'coverage_requirements' not in job):
            raise ValueError('claim_review_job_claim_changed')
        invoke_knowledge('project_description', {'project_root': job['evidence']['root'],
            'action': 'claim_review_' + job['schema_version'].rsplit('.', 1)[1], 'evidence': job['evidence'], 'claims': [job['claim']],
            'coverage_requirements': job['coverage_requirements']}, root=root)


def review_messages(job, *, root=ROOT):
    checked_job(job, root=root)
    extra = ({'coverage_requirements': job['coverage_requirements']}
             if not job['schema_version'].endswith('.v1') else {})
    if job['claim_namespace'] == 'final':
        extra['claim_namespace'] = 'final'
    if 'return_flag_analysis' in job:
        extra['return_flag_analysis'] = job['return_flag_analysis']
    if 'mechanism_contract' in job:
        extra['mechanism_contract'] = job['mechanism_contract']
    if 'return_property_analysis' in job:
        extra['return_property_analysis'] = job['return_property_analysis']
    return [{'role': 'system', 'content': job['instruction']},
            {'role': 'user', 'content': json.dumps({'claim': job['claim'], 'evidence': job['evidence'],
                'claim_packets': job['claim_packets'], **extra}, ensure_ascii=False)}]


def validate_claim_response(job, response, *, root=ROOT):
    structured = not job['schema_version'].endswith('.v1')
    extra = {'coverage_requirements': job['coverage_requirements']} if structured else {}
    contribution = (_mechanism_contribution(job, root=root, response=response) if 'mechanism_contract' in job else
        invoke_knowledge('project_description', {'project_root': job['evidence']['root'],
        'action': 'claim_review_' + job['schema_version'].rsplit('.', 1)[1] if structured else 'claim_review',
        'evidence': job['evidence'], 'claims': [job['claim']], 'claim_result': response, **extra}, root=root))
    validation = deepcopy(contribution['claim_validation'])
    if 'return_property' in job:
        from .description_return_property import contribution as property_contribution
        validation = deepcopy(property_contribution(job, root=root, response=response, validate=True)['claim_validation'])
    result = validation.pop('normalized_result', deepcopy(response))
    return result, validation


def run_claim_review(job, *, config=None, chat=None, root=ROOT):
    messages = review_messages(job, root=root)
    telemetry = []
    cfg = replace(config or description_model_config(), fallbacks=(),
                  max_output_tokens=3200 if not job['schema_version'].endswith('.v1') else 1600,
                  telemetry_sink=telemetry.append)
    receipt = {'schema_version': 'single_claim_review_receipt.v1', 'status': 'failed',
               'job': deepcopy(job), 'telemetry': telemetry, 'model_requests': 1,
               'execution_authorized': False, 'semantic_verified': False, 'proposal_only': True}
    try:
        response = (chat or call_json_chat)(messages, config=cfg)
        receipt['raw_response'] = response
        checked_job(job, root=root)
        result, validation = validate_claim_response(job, response, root=root)
        receipt.update(status='reviewed', result=result, **validation)
    except (LocalInferenceError, ValueError, OSError) as exc:
        receipt['reason'] = str(exc)
    receipt['digest'] = content_digest(receipt)
    return receipt
