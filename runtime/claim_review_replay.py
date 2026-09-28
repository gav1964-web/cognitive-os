"""Explicit offline projection of saved v2 responses; never a model receipt."""
from copy import deepcopy

from .competency_knowledge import invoke_knowledge
from .narrow_type_evidence_binding import content_digest
from .single_claim_review import checked_job


def replay_as_v3(receipt):
    if (receipt.get('schema_version') != 'single_claim_review_receipt.v1'
            or receipt.get('digest') != content_digest({k: v for k, v in receipt.items() if k != 'digest'})
            or receipt['job']['schema_version'] != 'single_claim_review_job.v2'):
        raise ValueError('replay_requires_intact_v2_receipt')
    job, raw = receipt['job'], receipt.get('raw_response')
    checked_job(job)
    if (not isinstance(raw, dict) or set(raw) - {'parts', 'coverage', 'proposed_text', 'verdict', 'reason', 'citations'}
            or not isinstance(raw.get('parts'), list)):
        raise ValueError('replay_invalid_source_response')
    parts, changes = [], ['remove redundant overall assessment; retain part assessments']
    for row in raw['parts']:
        if not isinstance(row, dict) or set(row) != {'text', 'verdict', 'reason', 'citations', 'counterexamples'}:
            raise ValueError('replay_invalid_source_part')
        part = {key: deepcopy(row[key]) for key in ('text', 'verdict', 'reason', 'citations')}
        if not isinstance(row['counterexamples'], list) or not isinstance(part['citations'], list):
            raise ValueError('replay_invalid_source_quotes')
        if row['counterexamples']:
            part['verdict'] = 'refuted'
            part['citations'] += [q for q in deepcopy(row['counterexamples']) if q not in part['citations']]
            changes.append('preserve v2 declared-counterexample refutation in part')
        parts.append(part)
    coverage = raw.get('coverage')
    if isinstance(coverage, dict):
        if any(not isinstance(row, dict) or row.get('id') != key for key, row in coverage.items()):
            raise ValueError('replay_coverage_key_mismatch')
        rows = list(coverage.values())
    elif isinstance(coverage, list):
        rows = coverage
    else:
        raise ValueError('replay_invalid_source_coverage')
    mapped = {}
    for row in rows:
        if (not isinstance(row, dict) or set(row) != {'id', 'status', 'reason', 'citations'}
                or not isinstance(row['id'], str) or row['id'] in mapped):
            raise ValueError('replay_invalid_source_coverage')
        mapped[row['id']] = {key: deepcopy(row[key]) for key in ('status', 'reason', 'citations')}
    response = {'parts': parts, 'coverage': mapped, 'proposed_text': raw.get('proposed_text')}
    changes.append('key coverage by existing unique IDs; do not infer new coverage assessments')
    result = {'schema_version': 'claim_contract_replay.v1', 'source_receipt_digest': receipt['digest'],
              'projected_response': response, 'operations': changes, 'model_calls': 0,
              'admissible_model_proposal': False, 'execution_authorized': False}
    try:
        contribution = invoke_knowledge('project_description', {'project_root': job['evidence']['root'],
            'action': 'claim_review_v3', 'claims': [job['claim']], 'evidence': job['evidence'],
            'coverage_requirements': job['coverage_requirements'], 'claim_result': response})
        result.update(status='validated_projection', validation=contribution['claim_validation'])
    except ValueError as exc:
        result.update(status='failed_projection', reason=str(exc))
    result['digest'] = content_digest(result)
    return result
