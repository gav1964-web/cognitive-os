"""Prepare claim checks from an immutable saved response, without model calls."""
from copy import deepcopy
import json

from .competency_knowledge import ROOT, invoke_knowledge
from .description_review_tasks import review_tasks
from .narrow_type_evidence_binding import content_digest
from .project_description import _sources_current
from .description_shape import report_draft
from .project_description_review import draft_claims


def audit_saved_description(report, *, root=ROOT):
    evidence = report['evidence']
    if not _sources_current(evidence):
        raise ValueError('description_offline_stale_sources')
    draft = report_draft(report, root=root)
    claims = draft_claims(draft)
    response = report.get('review_response', {})
    reviews = report.get('claim_reviews', response.get('claim_reviews') if isinstance(response, dict) else None)
    payload = {'project_root': evidence['root'], 'action': 'review', 'evidence': evidence, 'claims': claims}
    if reviews is not None:
        payload['reviews'] = reviews
        if report.get('review_request'):
            payload['review_evidence'] = json.loads(report['review_request'][1]['content'])['evidence']
    result = invoke_knowledge('project_description', payload, root=root)
    audit = result.get('review_audit', {
        'schema_version': 'description_review_audit.v1', 'status': 'review_not_completed',
        'semantic_verified': False, 'automatic_claim_restoration': False,
        'findings': [{'claim_id': claim['id'], 'kind': 'review_not_completed', 'matches': []}
                     for claim in claims]})
    prepared = {**report, 'review_audit': audit, 'claim_reviews': reviews or []}
    if not _sources_current(evidence):
        raise ValueError('description_offline_stale_sources')
    return {'schema_version': 'description_offline_review.v1', 'source_report_digest': content_digest(report),
            'project_root': evidence['root'], 'original_status': report['status'],
            'draft_claims': deepcopy(claims), 'evidence': result['evidence'],
            'claim_packets': result['claim_packets'], 'context_characters': result['context_characters'],
            'review_audit': audit, 'review_tasks': review_tasks(prepared, claims),
            'model_requests': 0, 'execution_authorized': False}
