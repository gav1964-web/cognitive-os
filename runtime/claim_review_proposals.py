"""Attach reviewed proposals without changing accepted product facts or closing tasks."""
from copy import deepcopy

from .narrow_type_evidence_binding import content_digest
from .single_claim_review import checked_job, validate_claim_response


def checked_proposal(proposal, *, report=None):
    if (proposal.get('schema_version') != 'single_claim_review_receipt.v1'
            or proposal.get('status') != 'reviewed' or proposal.get('proposal_only') is not True
            or proposal.get('semantic_verified') is not False or proposal.get('execution_authorized') is not False
            or proposal.get('digest') != content_digest({k: v for k, v in proposal.items() if k != 'digest'})):
        raise ValueError('invalid_claim_review_proposal')
    checked_job(proposal['job'])
    job = proposal['job']
    result, validation = validate_claim_response(job, proposal['raw_response'])
    if result != proposal['result'] or any(proposal.get(k) != v for k, v in validation.items()):
        raise ValueError('claim_review_result_changed')
    if report is not None and proposal['job']['source_report_digest'] != content_digest(report):
        raise ValueError('claim_review_wrong_report')
    if report is not None:
        from .description_claim_namespace import report_claims
        originals = report_claims(report, job['claim_namespace'])
        if job['original_claim'] not in originals:
            raise ValueError('claim_review_wrong_namespace_or_claim')
    return deepcopy(proposal)


def attach_proposals(audit, proposals, *, decisions=None):
    result = deepcopy(audit)
    accepted = []
    for proposal in proposals:
        checked = checked_proposal(proposal)
        if checked['job']['source_report_digest'] != audit['source_report_digest']:
            raise ValueError('claim_review_wrong_report')
        if any(row['job']['digest'] == checked['job']['digest'] for row in accepted):
            raise ValueError('duplicate_claim_review_proposal')
        accepted.append(checked)
    result['review_proposals'] = accepted
    for task in result['review_tasks']:
        task['proposal_digests'] = [row['digest'] for row in accepted
                                   if row['job']['original_claim']['id'] == task['claim_id']
                                   and row['job']['claim_namespace'] == task.get('claim_namespace', 'draft')]
    if decisions is not None:
        from .claim_review_decisions import checked_decisions
        result['review_decisions'] = checked_decisions(decisions, report_digest=audit['source_report_digest'])
    result['execution_authorized'] = False
    return result
