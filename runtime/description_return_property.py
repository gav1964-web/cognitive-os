"""Coordinate plugin-owned explicit properties; never trust a saved analysis alone."""
from .competency_knowledge import ROOT, invoke_knowledge


def contribution(job, *, root=ROOT, response=None, validate=False):
    payload = {'project_root': job['evidence']['root'], 'action': 'return_property',
               'evidence': job['evidence'], 'claims': [job['claim']],
               'coverage_requirements': job['coverage_requirements'],
               'return_property': job['return_property']}
    if validate:
        payload['claim_result'] = response
    return invoke_knowledge('project_description', payload, root=root)


def bind(job, selector, *, root=ROOT):
    success = isinstance(selector, dict) and selector.get('kind') == 'return_field_equals_for_inputs'
    invocation = success or (isinstance(selector, dict) and selector.get('kind') == 'normal_return_for_inputs')
    keys = {'path', 'symbol', 'claim_start', 'claim_end', 'kind', 'inputs' if invocation else 'field'}
    if success:
        keys |= {'field', 'expected'}
    known = {s['path']: s['sha256'] for s in job['evidence']['sources']}
    if (not isinstance(selector, dict) or set(selector) != keys
            or not isinstance(selector.get('path'), str) or selector['path'] not in known):
        raise ValueError('return_property_selector_not_in_job_sources')
    job['return_property'] = {**selector, 'sha256': known[selector['path']]}
    result = contribution(job, root=root)
    job['return_property_analysis'] = result['return_property_analysis']
    job['instruction'] = result['instruction']


def check(job, *, root=ROOT):
    keys = {'return_property', 'return_property_analysis'}
    present = keys.intersection(job)
    if not present:
        return
    if (present != keys or job['schema_version'] != 'single_claim_review_job.v4'
            or 'mechanism_contract' in job or 'return_flag_analysis' in job):
        raise ValueError('return_property_requires_separate_v4_job')
    known = {s['path']: s['sha256'] for s in job['evidence']['sources']}
    property = job['return_property']
    if not isinstance(property, dict) or known.get(property.get('path')) != property.get('sha256'):
        raise ValueError('return_property_source_changed')
    expected = contribution(job, root=root)
    if (job['return_property_analysis'] != expected['return_property_analysis']
            or job['instruction'] != expected['instruction']):
        raise ValueError('return_property_evidence_or_instruction_changed')
