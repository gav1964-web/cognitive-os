"""Explicit reviewer-selected invocation facts for full descriptions, not claims."""
from copy import deepcopy

from .source_lookup import read_requests
from .helper_context import sections
from .api_inputs import analyze_inputs


def build(root, evidence, checks, policy):
    if not isinstance(checks, list) or not 1 <= len(checks) <= 6:
        raise ValueError('bounded_behavior_checks_required')
    rows = []
    sources = {r['path']: r for r in evidence['sources']}
    for check in checks:
        if (not isinstance(check, dict) or set(check) != {'path','sha256','symbol','inputs','field','expected'}
                or not isinstance(check['path'], str) or check['path'] not in sources
                or check['sha256'] != sources[check['path']]['sha256']
                or not isinstance(check['symbol'], str) or not check['symbol'].isidentifier()):
            raise ValueError('source_bound_behavior_check_required')
        source = read_requests(root, [{k:check[k] for k in ('path','sha256','symbol')}], policy)[0]
        spans = sections(source['excerpt'])
        complete = (sum(s['name'] == check['symbol'] for s in spans) == 1
            and not source.get('helper_context', {}).get('caller_truncated', True)
            and all(s['complete'] for s in spans))
        analysis = (analyze_inputs('\n\n'.join(s['text'].split('\n',1)[1] for s in spans),
            check['symbol'], check['inputs'], success={k:check[k] for k in ('field','expected')}) if complete else
            {'status':'unknown','complete':False,'reason':'complete_function_context_required',
             'source_executed':False,'semantic_verified':False})
        rows.append({'selector':deepcopy(check),'evidence_id':sources[check['path']]['id'],'analysis':analysis})
    return {'schema_version':'description_behavior_checks.v1','checks':rows,
        'selection_origin':'explicit_reviewer_supplied','claim_binding':'not_established',
        'semantic_verified':False,'source_executed':False}
