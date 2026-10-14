"""Restore a rejected, unqualified draft without promoting it to acceptance."""
import json
from pathlib import Path

from .feature_checkpoint import load_roles, qualified_spec, rejected_candidate, verified_candidate, pending_spec
from .narrow_type_evidence_binding import content_digest
from .feature_quality_draft import draft_binding, audit_policy_matches, historical_audit
from .feature_workspace import read_sources
from .feature_audit_history import load_history, save_history, merge_history


def restore_prior_frozen(q, checkpoint, project, expected, goal, *, _seen=None):
    """Retain earlier native-qualified tests across intervening rejected drafts."""
    checkpoint = Path(checkpoint).resolve()
    seen = set(_seen or ())
    if checkpoint in seen or len(seen) >= 16:
        raise ValueError('quality_resume_frozen_history_cycle_or_depth')
    seen.add(checkpoint)
    path = checkpoint.parent / 'report.json'
    if not path.is_file():
        return
    journal = json.loads(path.read_text(encoding='utf-8'))
    if journal.get('goal') != goal or journal.get('source_hashes') != expected:
        raise ValueError('quality_resume_journal_identity')
    ancestors = {Path(journal[key]).resolve() for key in (
        'resumed_unqualified_spec', 'resumed_native_rejected_spec', 'resumed_qualified_spec',
        'resumed_rejected_review') if journal.get(key)}
    if len(ancestors) > 1:
        raise ValueError('quality_resume_ambiguous_frozen_ancestor')
    for ancestor in ancestors:
        roles, _ = load_roles(ancestor, project, expected, goal)
        restore_prior_frozen(q, ancestor, project, expected, goal, _seen=seen)
        spec = qualified_spec(ancestor)
        if spec:
            prior = json.loads((ancestor / 'report.json').read_text(encoding='utf-8'))
            if prior.get('attempts'):
                verified_candidate(ancestor, require_passed=prior['attempts'][-1]['passed'])
            incoming = {t['path']: t['content'] for t in spec['accepted']['tests']}
            if any(incoming.get(t['path']) != t['content'] for t in q.frozen):
                raise ValueError('quality_resume_frozen_history_changed')
            q.freeze_specification(spec['accepted'], goal=goal, design=roles['architect'], source_hashes=expected)
            q.record('ancestor_frozen_tests_restored', checkpoint=str(ancestor), grants_approval=False)
    frozen, origin, accepted, design = q.frozen, None, None, None
    for item in journal.get('cycles', []):
        prior = Path(item['checkpoint']).resolve()
        if prior == checkpoint:
            break
        if prior.parent != checkpoint.parent:
            raise ValueError('quality_resume_cycle_outside_journal')
        roles, _ = load_roles(prior, project, expected, goal)
        spec = qualified_spec(prior)
        if spec:
            verified_candidate(prior)
            incoming = {t['path']: t['content'] for t in spec['accepted']['tests']}
            if any(incoming.get(t['path']) != t['content'] for t in frozen):
                raise ValueError('quality_resume_frozen_history_changed')
            frozen, origin = spec['accepted']['tests'], prior
            accepted, design = spec['accepted'], roles['architect']
    if accepted is not None:
        q.freeze_specification(accepted, goal=goal, design=design, source_hashes=expected)
        q.record('prior_frozen_tests_restored', checkpoint=str(origin))


def restore_native_rejected_spec(q, checkpoint, project, expected, goal):
    roles, _ = load_roles(checkpoint, project, expected, goal)
    proposal = pending_spec(checkpoint)
    if proposal is None:
        raise ValueError('quality_resume_requires_native_rejected_spec')
    restore_prior_frozen(q, checkpoint, project, expected, goal)
    if restore_post_native_audit(q, checkpoint, project, expected, goal, proposal):
        return str(checkpoint)
    from .feature_spec_metadata import repair_spec_metadata
    _, changes = repair_spec_metadata(proposal, expected, q.work / 'resume-metadata-proposal.json')
    if changes:
        q.unaccepted['spec_writer'] = {'binding': draft_binding({
            'goal': goal, 'artifacts': roles, 'source_inventory_digest': content_digest(expected)},
            'spec_writer'), 'proposal': proposal}
    q.record('native_rejected_spec_restored', checkpoint=str(checkpoint))
    return str(checkpoint)


def restore_post_native_audit(q, checkpoint, project, expected, goal, rejected):
    """Prefer a bound later audited correction over the older native failure."""
    transcript = Path(checkpoint).parent.parent / 'transcript.json'
    if not transcript.is_file():
        return False
    rows = json.loads(transcript.read_text(encoding='utf-8'))
    index = next((i for i in range(len(rows)-1, -1, -1) if any(
        e.get('provider_label') == 'quality:spec_auditor' for e in rows[i].get('telemetry', []))), None)
    if index is None or rows[index].get('raw_response', {}).get('decision') != 'reject':
        return False
    writer = next((r for r in reversed(rows[:index]) if r.get('status') == 'returned'
        and r.get('raw_response', {}).get('status') == 'ready' and any(
        e.get('provider_label') == 'feature:spec_writer' for e in r.get('telemetry', []))), None)
    if writer is None:
        return False
    payload = json.loads(writer['messages'][1]['content'])
    if 'test_reference_contract' in payload:
        from .feature_test_references import expand_test_references
        payload = expand_test_references(payload)
    if payload.get('feedback', {}).get('rejected_spec') != rejected:
        return False  # No proof this draft was a response to this native failure.
    roles, _ = load_roles(checkpoint, project, expected, goal)
    if draft_binding(payload, 'spec_writer') != draft_binding({'goal': goal,
            'artifacts': roles, 'source_inventory_digest': content_digest(expected)}, 'spec_writer'):
        raise ValueError('quality_resume_post_native_writer_identity')
    restore_spec_draft(q, checkpoint, project, expected, goal)
    q.record('post_native_audit_restored', checkpoint=str(checkpoint), grants_approval=False)
    return True


def restore_rejected_review(q, checkpoint, project, expected, goal):
    checkpoint = Path(checkpoint).resolve()
    load_roles(checkpoint, project, expected, goal)
    report = json.loads((checkpoint / 'report.json').read_text(encoding='utf-8'))
    candidate = rejected_candidate(checkpoint)
    spec = qualified_spec(checkpoint)
    if (not candidate or not candidate.get('review') or not spec
            or not report.get('reason', '').startswith('feature_review_rejected:')):
        raise ValueError('quality_resume_requires_rejected_review')
    q.freeze_specification(spec['accepted'], goal=goal, design=report['artifacts']['architect'], source_hashes=expected)
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
    later_unaudited = (audit_index is not None and not writer_transcript and not audit_transcript
        and rows[audit_index].get('raw_response', {}).get('decision') == 'approve'
        and any(r.get('status') == 'returned' and r.get('raw_response', {}).get('status') == 'ready'
            and any(e.get('provider_label') == 'feature:spec_writer' for e in r.get('telemetry', []))
            for r in rows[audit_index + 1:]))
    if audit_index is None or later_unaudited:
        # A budget stop can follow a complete paid draft before its first audit.
        # Restore it only through the same source/goal/design binding checks.
        restore_prior_frozen(q, checkpoint, project, expected, goal)
        restore_unaccepted_proposal(q, checkpoint, project, expected, goal, transcript)
        q.record('unreviewed_draft_restored', checkpoint=str(checkpoint), grants_approval=False)
        return str(checkpoint)
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
    writer_payload = json.loads(writer['messages'][1]['content'])
    from .feature_frozen_references import expand_frozen_references
    from plugins.development_quality.src.spec_metadata import repair_metadata
    from .feature_spec_delta import expand as expand_spec_delta
    from .feature_test_references import expand_test_references
    if 'test_reference_contract' in writer_payload:
        writer_payload = expand_test_references(writer_payload)
    if ('specification_delta' in writer['raw_response'] and draft_binding(writer_payload, 'spec_writer')
            != draft_binding({'goal': goal, 'artifacts': roles,
                'source_inventory_digest': content_digest(expected)}, 'spec_writer')):
        raise ValueError('quality_resume_writer_identity')
    expanded, _ = expand_frozen_references(expand_spec_delta(writer['raw_response'], writer_payload), writer_payload.get('immutable_previous_tests', []),
        allow_separate=payload.get('frozen_reference_contract') == 'separate_frozen_refs.v1')
    normalized = repair_metadata(expanded, sorted(expected))['artifact']
    if 'immutable_baseline_expectations' in writer_payload:
        from .feature_accepted_metadata import restore
        restore_prior_frozen(q, checkpoint, project, expected, goal)
        if (not q.accepted_metadata or writer_payload['immutable_baseline_expectations']
                != q.accepted_metadata['baseline_expectations']
                or writer_payload.get('immutable_case_plan', q.accepted_metadata['case_plan'])
                != q.accepted_metadata['case_plan']):
            raise ValueError('quality_resume_accepted_metadata_mismatch')
        normalized, _ = restore(normalized, q.accepted_metadata, draft_binding(writer_payload, 'spec_writer'),
            allow_label_correction=payload.get('accepted_metadata_contract') == 'qualified_label_repair.v1')
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
            or payload['specification'] != normalized
            or writer['raw_response'].get('status') != 'ready'
            or audit['raw_response'].get('decision') != 'reject'):
        raise ValueError('quality_resume_draft_identity')
    q.pending['spec_writer'] = {
        'binding': draft_binding({'goal': goal, 'artifacts': roles,
                                  'source_inventory_digest': content_digest(expected)}, 'spec_writer'),
        'feedback': {'rejected': normalized,
            'issues': [{'acceptance_audit': audit['raw_response']}],
            'instruction': 'Repair this unaccepted draft. Fresh audit and native qualification remain mandatory.'}}
    q.record('unaccepted_draft_restored', role='spec_writer', checkpoint=str(checkpoint),
             transcript=str(transcript), writer_transcript=str(writer_transcript or transcript),
             audit_digest=audit['request_digest'], writer_digest=writer['request_digest'])
    restore_prior_frozen(q, checkpoint, project, expected, goal)
    old_instruction = audit['messages'][0].get('content', '')
    policy_changed = not audit_policy_matches(old_instruction, q.policy['spec_auditor'])
    feedback = q.pending['spec_writer']['feedback']
    binding = q.pending['spec_writer']['binding']
    history = merge_history(load_history(checkpoint.parent, binding), payload.get('historical_audits', []))
    if policy_changed:
        history.append(historical_audit(audit, payload))
        feedback['issues'] = []
        feedback['instruction'] = (
            'The previous rejection used a different auditor policy. Follow only current '
            'contract defects; historical demands require fresh auditor confirmation. '
            'Preserve the draft coverage and frozen tests; fresh audit and native gates remain mandatory.')
        q.record('unaccepted_draft_policy_reaudit', checkpoint=str(checkpoint),
                 audit_digest=audit['request_digest'], grants_approval=False)
    elif payload.get('prior_audit_issues'):
        feedback['prior_audit_issues'] = payload['prior_audit_issues']
    if history:
        feedback['historical_audits'] = history
        save_history(q.work, binding, history)
    newer_writer = any(
            r.get('status') == 'returned' and r.get('raw_response', {}).get('status') == 'ready'
            and any(e.get('provider_label') == 'feature:spec_writer' for e in r.get('telemetry', []))
            for r in rows[audit_index + 1:])
    if not writer_transcript and not audit_transcript and (newer_writer or policy_changed):
        restore_unaccepted_proposal(q, checkpoint, project, expected, goal, transcript)
    elif policy_changed:
        # Explicit split receipts already bind this normalized draft to the audit.
        q.unaccepted['spec_writer'] = {
            'binding': q.pending['spec_writer']['binding'], 'proposal': normalized}
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
    from .feature_spec_delta import expand as expand_spec_delta
    from .feature_test_references import expand_test_references
    if 'test_reference_contract' in payload:
        payload = expand_test_references(payload)
    binding = draft_binding({'goal': goal, 'artifacts': roles,
                            'source_inventory_digest': content_digest(expected)}, 'spec_writer')
    if draft_binding(payload, 'spec_writer') != binding:
        raise ValueError('quality_resume_proposal_identity')
    if q.frozen != payload.get('immutable_previous_tests', []):
        raise ValueError('quality_resume_proposal_frozen_context_mismatch')
    if payload.get('quality_feedback'):
        q.feedback = payload['quality_feedback']  # Advisory context, never approval.
    history = load_history(checkpoint.parent, binding)
    history_digest = payload.get('quality_contract_feedback', {}).get('historical_audits_digest')
    if history_digest and history_digest != content_digest(history):
        raise ValueError('quality_resume_audit_history_integrity')
    proposal = expand_spec_delta(row['raw_response'], payload)
    if history and 'spec_writer' not in q.pending:
        from .feature_frozen_references import expand_frozen_references, repair_reference_metadata
        previous, _ = repair_reference_metadata(proposal, q.frozen)
        previous, _ = expand_frozen_references(previous, q.frozen)
        q.pending['spec_writer'] = {'binding': binding, 'feedback': {
            'rejected': previous, 'issues': [], 'historical_audits': history,
            'instruction': 'Fresh audit of historical concerns and native qualification are mandatory.'}}
        save_history(q.work, binding, history)
    q.unaccepted['spec_writer'] = {'binding': binding, 'proposal': proposal}
    q.record('unaccepted_proposal_restored', checkpoint=str(checkpoint),
             transcript=str(transcript), request_digest=row['request_digest'])


def restore_qualified_spec(q, checkpoint, project, expected, goal):
    """Resume a native-qualified stage; native gates still run before coding."""
    checkpoint = Path(checkpoint).resolve()
    load_roles(checkpoint, project, expected, goal)
    report = json.loads((checkpoint / 'report.json').read_text(encoding='utf-8'))
    spec = qualified_spec(checkpoint)
    allowed = report.get('status') == 'spec_qualified' or (
        report.get('status') == 'blocked' and report.get('reason') in
        ('feature_frozen_test_echo_changed', 'feature_call_count_exhausted',
         'feature_next_call_budget_exhausted', 'feature_stop_requested'))
    if not allowed and spec:
        from .feature_programmer_syntax import restored_feedback
        allowed = restored_feedback(checkpoint, project, expected,
            {t['path']: t['content'].encode('utf-8') for t in spec['accepted']['tests']},
            report['artifacts']['architect']['scope']) is not None
    if (not allowed or report.get('attempts')
            or not spec or not report.get('frozen_test_hashes')):
        raise ValueError('quality_resume_requires_qualified_spec_boundary')
    q.freeze_specification(spec['accepted'], goal=goal, design=report['artifacts']['architect'], source_hashes=expected)
    q.record('qualified_spec_restored', checkpoint=str(checkpoint),
             frozen_test_hashes=report['frozen_test_hashes'])
    return str(checkpoint)


def restore_failed_candidate(q, checkpoint, project, expected, goal):
    """Resume a bound native assertion failure, never promote it to review-ready."""
    checkpoint = Path(checkpoint).resolve()
    report = json.loads((checkpoint / 'report.json').read_text(encoding='utf-8'))
    if (report.get('status') != 'blocked' or report.get('reason') not in
            ('feature_acceptance_failed', 'feature_candidate_no_progress')):
        return False
    load_roles(checkpoint, project, expected, goal)
    candidate = verified_candidate(checkpoint, require_passed=False)
    if report.get('artifacts', {}).get('reviewer') or not qualified_spec(checkpoint):
        raise ValueError('quality_resume_invalid_native_failure')
    q.freeze_specification(qualified_spec(checkpoint)['accepted'], goal=goal,
                           design=report['artifacts']['architect'], source_hashes=expected)
    q.record('native_failed_candidate_restored', checkpoint=str(checkpoint),
             candidate_hashes=candidate['candidate_hashes'], grants_approval=False)
    return True


def restore_pending_candidate(q, checkpoint, project, expected, goal):
    """Resume review after a settled call/budget stop, with full native recheck."""
    checkpoint = Path(checkpoint).resolve()
    report = json.loads((checkpoint / 'report.json').read_text(encoding='utf-8'))
    if not report.get('attempts'):
        return False
    review = report.get('artifacts', {}).get('reviewer')
    pending = (report.get('status') == 'blocked' and report.get('reason') in (
        'feature_call_count_exhausted', 'feature_next_call_budget_exhausted',
        'feature_stop_requested') and review is None)
    completed = (report.get('status') == 'verified'
                 and isinstance(review, dict) and review.get('decision') == 'approve')
    if not (pending or completed):
        raise ValueError('quality_resume_requires_pending_candidate_review')
    if completed and json.loads((checkpoint / 'reviewer.json').read_text(encoding='utf-8')) != review:
        raise ValueError('quality_resume_completed_review_changed')
    load_roles(checkpoint, project, expected, goal)
    verified_candidate(checkpoint)
    spec = qualified_spec(checkpoint)
    if not spec:
        raise ValueError('quality_resume_requires_frozen_spec')
    q.freeze_specification(spec['accepted'], goal=goal, design=report['artifacts']['architect'], source_hashes=expected)
    q.record('pending_candidate_restored', checkpoint=str(checkpoint), grants_approval=False)
    return True
