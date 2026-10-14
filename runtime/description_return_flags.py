"""Bind opt-in conditional suffix evidence to the same sources as a claim job."""
from .competency_knowledge import ROOT, invoke_knowledge

def prepare_flags(selectors, evidence, *, root=ROOT):
    if not isinstance(selectors, list) or not 1 <= len(selectors) <= 3:
        raise ValueError('return_flag_selectors_required')
    known = {r['path']: r['sha256'] for r in evidence['sources']}
    requests = []
    for row in selectors:
        if (not isinstance(row, dict) or set(row) != {'path', 'symbol'}
                or not isinstance(row['path'], str) or row['path'] not in known
                or not isinstance(row['symbol'], str) or not row['symbol'].isidentifier()):
            raise ValueError('return_flag_selector_not_in_job_sources')
        requests.append({**row, 'sha256': known[row['path']]})
    result = invoke_knowledge('project_description', {'project_root': evidence['root'],
        'action': 'return_flags', 'requests': requests}, root=root)
    return requests, result['return_flag_analysis'], result['instruction'], result['coverage_requirements'][0]


def check_flags(job, *, root=ROOT):
    keys = {'return_flag_requests', 'return_flag_analysis'}
    present = keys.intersection(job)
    if not present:
        return
    if present != keys or job['schema_version'] != 'single_claim_review_job.v4':
        raise ValueError('return_flag_requires_complete_v4_job')
    bound = job['return_flag_requests']
    if (not isinstance(bound, list) or any(not isinstance(r, dict)
            or set(r) != {'path', 'symbol', 'sha256'} for r in bound)):
        raise ValueError('invalid_return_flag_binding')
    requests, expected, _, requirement = prepare_flags([{k: r[k] for k in ('path', 'symbol')} for r in bound],
                                                       job['evidence'], root=root)
    if requirement not in job.get('coverage_requirements', []):
        raise ValueError('return_flag_coverage_required')
    if requests != bound or job['return_flag_analysis'] != expected:
        raise ValueError('return_flag_evidence_changed')
