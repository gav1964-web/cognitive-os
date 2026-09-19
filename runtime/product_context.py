"""Reviewed product meaning carried as advisory context, never patch authority."""
from copy import deepcopy
import hashlib
from pathlib import Path

from .narrow_type_evidence_binding import content_digest
from .project_description import _sources_current
from .project_description_review import draft_claims


def make_product_context(report, *, accepted_claim_ids, reviewer, notes=None, constraints=None,
                         review_proposals=None, review_decisions=None):
    if report.get('status') != 'described' or not reviewer or not isinstance(reviewer, str):
        raise ValueError('product_context_review_required')
    evidence = report['evidence']
    from .description_shape import checked_report_description
    description = checked_report_description(report)
    available = {row['id']: row for row in draft_claims(description)}
    if (not isinstance(accepted_claim_ids, list) or not accepted_claim_ids
            or any(not isinstance(key, str) for key in accepted_claim_ids)
            or len(set(accepted_claim_ids)) != len(accepted_claim_ids)
            or any(key not in available for key in accepted_claim_ids)
            or 'purpose' not in accepted_claim_ids):
        raise ValueError('product_context_explicit_claim_review_required')
    if not _sources_current(evidence):
        raise ValueError('product_context_stale_sources')
    from .description_grounding import description_grounding
    grounding = description_grounding(description, evidence)
    unsupported = {r['claim_id'] for r in grounding['claims'] if r['status'] != 'implementation_cited'}
    if unsupported.intersection(accepted_claim_ids):
        raise ValueError('product_context_implementation_evidence_required')
    from .claim_review_proposals import checked_proposal
    proposals = [checked_proposal(row, report=report) for row in (review_proposals or [])]
    packet = {'schema_version': 'product_context.v1', 'project_root': evidence['root'],
              'description_digest': content_digest(description),
              'claims': [deepcopy(available[key]) for key in accepted_claim_ids],
              'unknowns': deepcopy(description['unknowns']),
              'owner_statements': deepcopy(report.get('owner_notes', [])),
              'constraints': list(constraints or []), 'review_notes': list(notes or []),
              'review_gaps': deepcopy(report.get('review_changes', [
                  row for row in report.get('claim_reviews', [])
                  if row['claim_id'] in report.get('unverified_removals', [])])),
              'review_tasks': deepcopy(report.get('review_tasks', [])),
              'review_proposals': proposals,
              'reviewed_by': reviewer, 'review_authority': 'caller_attestation_not_independent_certification',
              'sources': [{k: row[k] for k in ('id', 'path', 'sha256')} for row in evidence['sources']],
              'execution_authorized': False, 'authority': 'advisory_product_understanding'}
    if review_decisions is not None:
        from .claim_review_decisions import checked_decisions
        packet['source_report_digest'] = content_digest(report)
        packet['review_decisions'] = checked_decisions(review_decisions, report_digest=content_digest(report))
    packet['digest'] = content_digest(packet)
    return packet


def checked_product_context(packet, project):
    if (not isinstance(packet, dict) or packet.get('schema_version') != 'product_context.v1'
            or packet.get('execution_authorized') is not False
            or packet.get('authority') != 'advisory_product_understanding'
            or packet.get('review_authority') != 'caller_attestation_not_independent_certification'
            or not packet.get('reviewed_by') or not packet.get('claims') or not packet.get('sources')
            or packet.get('digest') != content_digest({k: v for k, v in packet.items() if k != 'digest'})):
        raise ValueError('invalid_product_context')
    project = Path(project).resolve()
    if project != Path(packet['project_root']).resolve():
        raise ValueError('product_context_wrong_project')
    from .claim_review_proposals import checked_proposal
    for proposal in packet.get('review_proposals', []):
        checked_proposal(proposal)
        if Path(proposal['job']['evidence']['root']).resolve() != project:
            raise ValueError('product_context_wrong_project')
    if 'review_decisions' in packet:
        from .claim_review_decisions import checked_decisions
        if not isinstance(packet.get('source_report_digest'), str):
            raise ValueError('product_context_missing_report_digest')
        ledger = checked_decisions(packet['review_decisions'], report_digest=packet['source_report_digest'])
        for event in ledger['events']:
            if Path(event['proposal']['job']['evidence']['root']).resolve() != project:
                raise ValueError('product_context_wrong_project')
    for row in packet['sources']:
        path = (project / row['path']).resolve()
        if (not path.is_relative_to(project) or not path.is_file()
                or hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']):
            raise ValueError('product_context_stale_sources')
    return deepcopy(packet)


def forward_product_context(artifact, incoming, project):
    if 'product_context' in incoming:
        artifact['product_context'] = checked_product_context(incoming['product_context'], project)
        artifact.setdefault('reasoning_provenance', {})['product_context'] = (
            'reviewed_source_bound_advisory; not verified requirements or execution authority')
    return artifact
