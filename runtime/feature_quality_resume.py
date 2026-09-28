"""Restore a rejected, unqualified draft without promoting it to acceptance."""
import json
from pathlib import Path

from .feature_checkpoint import load_roles, qualified_spec, rejected_candidate
from .narrow_type_evidence_binding import content_digest
from .feature_quality_draft import draft_binding
from .feature_workspace import read_sources


def restore_rejected_review(q, checkpoint, project, expected, goal):
    checkpoint = Path(checkpoint).resolve()
    load_roles(checkpoint, project, expected, goal)
    report = json.loads((checkpoint / 'report.json').read_text(encoding='utf-8'))
    candidate = rejected_candidate(checkpoint)
    spec = qualified_spec(checkpoint)
    if (not candidate or not candidate.get('review') or not spec
            or not report.get('reason', '').startswith('feature_review_rejected:')):
        raise ValueError('quality_resume_requires_rejected_review')
    q.frozen = spec['accepted']['tests']
    q.record('rejected_review_restored', checkpoint=str(checkpoint),
             candidate_hashes=candidate['candidate_hashes'])
    return report, candidate


def restore_spec_draft(q, checkpoint, project, expected, goal, *,
                       writer_transcript=None, audit_transcript=None):
    checkpoint = Path(checkpoint).resolve()
    report = json.loads((checkpoint / 'report.json').read_text(encoding='utf-8'))
    if report.get('attempts') or 'spec_writer' in report.get('artifacts', {}):
        raise ValueError('quality_resume_requires_unqualified_spec')
    roles, _ = load_roles(checkpoint, project, expected, goal)
    journal_path = checkpoint.parent / 'report.json'
    if journal_path.is_file():
        journal = json.loads(journal_path.read_text(encoding='utf-8'))
        if journal['goal'] != goal or journal['source_hashes'] != expected:
            raise ValueError('quality_resume_journal_identity')
    elif not (writer_transcript and audit_transcript):
        raise ValueError('quality_resume_missing_journal')
    transcript = Path(audit_transcript) if audit_transcript else checkpoint.parent.parent / 'transcript.json'
    rows = json.loads(transcript.read_text(encoding='utf-8'))
    audit_index = next((i for i in range(len(rows) - 1, -1, -1)
        if any(e.get('provider_label') == 'quality:spec_auditor'
               for e in rows[i].get('telemetry', []))), None)
    if audit_index is None:
        raise ValueError('quality_resume_missing_spec_audit')
    audit = rows[audit_index]
    writers = (json.loads(Path(writer_transcript).read_text(encoding='utf-8'))
               if writer_transcript else rows[:audit_index])
    writer = next((r for r in reversed(writers)
        if any(e.get('provider_label') == 'feature:spec_writer'
               for e in r.get('telemetry', [])) and r.get('raw_response', {}).get('status') == 'ready'), None)
    for row in (audit, writer):
        if (not row or row.get('status') != 'returned'
                or row.get('request_digest') != content_digest(row.get('messages'))):
            raise ValueError('quality_resume_transcript_integrity')
    payload = json.loads(audit['messages'][1]['content'])
    if writer_transcript:
        writer_payload = json.loads(writer['messages'][1]['content'])
        if (writer_payload.get('goal') != goal
                or writer_payload.get('artifacts', {}).get('architect') != roles['architect']):
            raise ValueError('quality_resume_writer_identity')
    for src in payload.get('sources', []):
        actual = read_sources(project, expected, [src], max_bytes=128000)[0]
        if actual['content'] != src['content'] or actual['end'] != src['end']:
            raise ValueError('quality_resume_source_excerpt_changed')
    if (payload['goal'] != goal or payload['design'] != roles['architect']
            or payload['specification'] != writer['raw_response']
            or writer['raw_response'].get('status') != 'ready'
            or audit['raw_response'].get('decision') != 'reject'):
        raise ValueError('quality_resume_draft_identity')
    q.pending['spec_writer'] = {
        'binding': draft_binding({'goal': goal, 'artifacts': roles,
                                  'source_inventory_digest': content_digest(expected)}, 'spec_writer'),
        'feedback': {'rejected': writer['raw_response'],
            'issues': [{'acceptance_audit': audit['raw_response']}],
            'instruction': 'Repair this unaccepted draft. Fresh audit and native qualification remain mandatory.'}}
    q.record('unaccepted_draft_restored', role='spec_writer', checkpoint=str(checkpoint),
             transcript=str(transcript), writer_transcript=str(writer_transcript or transcript),
             audit_digest=audit['request_digest'], writer_digest=writer['request_digest'])
    return str(checkpoint)


def restore_unaccepted_proposal(q, checkpoint, project, expected, goal, transcript):
    """Revalidate a paid writer response; it grants neither audit nor native approval."""
    roles, _ = load_roles(checkpoint, project, expected, goal)
    rows = json.loads(Path(transcript).read_text(encoding='utf-8'))
    row = next((r for r in reversed(rows) if r.get('status') == 'returned'
        and r.get('raw_response', {}).get('status') == 'ready'
        and any(e.get('provider_label') == 'feature:spec_writer' for e in r.get('telemetry', []))), None)
    if not row or row.get('request_digest') != content_digest(row.get('messages')):
        raise ValueError('quality_resume_proposal_integrity')
    payload = json.loads(row['messages'][1]['content'])
    binding = draft_binding({'goal': goal, 'artifacts': roles,
                            'source_inventory_digest': content_digest(expected)}, 'spec_writer')
    if draft_binding(payload, 'spec_writer') != binding:
        raise ValueError('quality_resume_proposal_identity')
    q.unaccepted['spec_writer'] = {'binding': binding, 'proposal': row['raw_response']}
    q.record('unaccepted_proposal_restored', checkpoint=str(checkpoint),
             transcript=str(transcript), request_digest=row['request_digest'])
