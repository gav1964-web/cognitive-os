"""Explicit reviewer attestations, separate from proposals and accepted facts."""
from copy import deepcopy
from datetime import datetime, timezone

from .claim_review_proposals import checked_proposal
from .narrow_type_evidence_binding import content_digest


def _digest(value):
    return content_digest({k: v for k, v in value.items() if k != 'digest'})


def _validate_event(event, report_digest, previous):
    keys = {'proposal', 'disposition', 'reviewer', 'reason', 'accepted_text',
            'recorded_at', 'previous_digest', 'digest'}
    if not isinstance(event, dict) or set(event) != keys or event['digest'] != _digest(event):
        raise ValueError('invalid_claim_decision_event')
    proposal = checked_proposal(event['proposal'])
    if (proposal['job']['source_report_digest'] != report_digest
            or event['previous_digest'] != previous):
        raise ValueError('claim_decision_wrong_report_or_history')
    for key, limit in (('reviewer', 200), ('reason', 2000), ('recorded_at', 100)):
        if not isinstance(event[key], str) or not event[key].strip() or len(event[key]) > limit:
            raise ValueError('claim_decision_attestation_required')
    if event['disposition'] not in ('accepted', 'rejected', 'deferred'):
        raise ValueError('invalid_claim_decision_disposition')
    text = event['accepted_text']
    if event['disposition'] == 'accepted':
        candidates = [proposal['result'].get('proposed_text')]
        if proposal['result']['verdict'] == 'supported':
            candidates.append(proposal['job']['original_claim']['text'])
        if not isinstance(text, str) or not text.strip() or text not in candidates:
            raise ValueError('claim_decision_explicit_candidate_text_required')
    elif text is not None:
        raise ValueError('claim_decision_unaccepted_text')


def checked_decisions(ledger, *, report_digest=None):
    if (not isinstance(ledger, dict)
            or set(ledger) != {'schema_version', 'source_report_digest', 'events', 'digest',
                               'execution_authorized', 'authority'}
            or ledger['schema_version'] != 'claim_review_decisions.v1'
            or ledger['execution_authorized'] is not False
            or ledger['authority'] != 'reviewer_attestation_not_independent_certification'
            or ledger['digest'] != _digest(ledger)
            or (report_digest is not None and ledger['source_report_digest'] != report_digest)
            or not isinstance(ledger['events'], list) or not 1 <= len(ledger['events']) <= 32):
        raise ValueError('invalid_claim_decisions')
    previous = None
    for event in ledger['events']:
        _validate_event(event, ledger['source_report_digest'], previous)
        previous = event['digest']
    return deepcopy(ledger)


def record_review_decision(proposal, *, disposition, reviewer, reason, accepted_text=None, ledger=None):
    proposal = checked_proposal(proposal)
    report_digest = proposal['job']['source_report_digest']
    result = (checked_decisions(ledger, report_digest=report_digest) if ledger is not None else {
        'schema_version': 'claim_review_decisions.v1', 'source_report_digest': report_digest,
        'events': [], 'execution_authorized': False,
        'authority': 'reviewer_attestation_not_independent_certification'})
    event = {'proposal': proposal, 'disposition': disposition, 'reviewer': reviewer,
             'reason': reason, 'accepted_text': accepted_text,
             'recorded_at': datetime.now(timezone.utc).isoformat(),
             'previous_digest': result['events'][-1]['digest'] if result['events'] else None}
    event['digest'] = _digest(event)
    result['events'].append(event)
    result['digest'] = _digest(result)
    return checked_decisions(result)
