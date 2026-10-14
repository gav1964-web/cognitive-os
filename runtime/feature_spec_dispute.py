"""Native evidence and independent review for a narrow preservation-test dispute."""
import json
from dataclasses import replace

from plugins.development_quality.src.main import run as quality_contract
from .feature_acceptance import prepare, verify, save, execution_feedback
from .feature_checkpoint import load_roles, qualified_spec, rejected_candidate
from .feature_workspace import inventory, read_sources, materialize_edits
from .narrow_type_evidence_binding import content_digest


def _targets(change, outcomes):
    prefix = change['path'][:-3].replace('/', '.') + '::' + change['node']
    return {n for n in outcomes if n == prefix or n.startswith(prefix + '[')}


def preservation_outcomes(before, after, old_candidate, new_candidate, corrections):
    old, new = before['new_tests']['tests'], after['new_tests']['tests']
    if set(old) != set(new) or not new_candidate['passed']:
        raise ValueError('spec_revision_native_identities_or_candidate_failed')
    selected = set()
    for change in corrections:
        names = _targets(change, old)
        if (not names or not any(old[n] == 'failed' and old_candidate['tests'].get(n) == 'failed' for n in names)
                or any(new[n] != 'passed' for n in names)):
            raise ValueError('spec_revision_not_demonstrated_preservation')
        selected.update(names)
    if any(old[n] != new[n] for n in old.keys() - selected):
        raise ValueError('spec_revision_unrelated_baseline_changed')
    if before['regression']['tests'] != after['regression']['tests']:
        raise ValueError('spec_revision_regression_changed')


def resolve_dispute(q, result, config, *, project, expected, checkpoint, python, goal):
    """At most one proposal/audit per call; callers bound revisions per invocation.

    Passing probes alone never authorize a correction. Unsupported revisions or
    ambiguous preservation remain blocked, retaining the original specification.
    """
    work = q.work / f'spec-dispute-{q.cycle}'
    work.mkdir()
    load_roles(checkpoint, project, expected, goal)
    spec = qualified_spec(checkpoint)['accepted']
    candidate = rejected_candidate(checkpoint)
    if not candidate or candidate.get('review') or result['attempts'][-1]['passed']:
        raise ValueError('spec_revision_requires_native_failed_candidate')
    if inventory(project) != expected:
        raise ValueError('spec_revision_source_changed')
    allowed = result['artifacts']['architect']['scope']
    sources = []
    for name in allowed:
        if name in expected:
            sources.extend(read_sources(project, expected, [{'path': name}], max_bytes=50000))
    before = result['baseline']
    failed = result['attempts'][-1]
    payload = {'goal': goal, 'design': result['artifacts']['architect'], 'sources': sources,
        'frozen_specification': spec, 'baseline': execution_feedback(before['new_tests']),
        'candidate_failure': execution_feedback(failed),
        'programmer_objection': result.get('no_progress', {}).get('proposal', candidate['proposal']).get('reason'),
        'failed_candidates': [{'candidate_attempt': i, 'failure': execution_feedback(row)}
            for i, row in enumerate(result['attempts'], 1)],
        'authority': 'Propose only a preservation equality expected-literal correction; no approval, production edits or goal changes.'}
    save(work / 'input.json', payload)
    proposal = q.call([{'role': 'system', 'content': q.policy['spec_dispute_writer']},
        {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)}],
        replace(config, provider_label='quality:spec_dispute_writer'))
    save(work / 'proposal.json', proposal)
    if proposal.get('decision') != 'propose_revision':
        save(work / 'report.json', {'status': 'unresolved', 'proposal': proposal, 'grants_approval': False})
        return None
    ordinal = proposal.get('candidate_attempt', len(result['attempts']))
    if type(ordinal) is not int or not 1 <= ordinal <= len(result['attempts']):
        raise ValueError('spec_revision_candidate_selection_invalid')
    failed = result['attempts'][ordinal - 1]
    saved = json.loads((checkpoint / f'attempt-{ordinal}/verification.json').read_text(encoding='utf-8'))
    if saved != failed or failed.get('passed') is not False:
        raise ValueError('spec_revision_candidate_receipt_mismatch')
    candidate = {'proposal': json.loads((checkpoint / f'proposal-{ordinal}.json').read_text(encoding='utf-8'))}
    revised = quality_contract({'action': 'revise_preservation_assertions', 'artifact': spec,
        'proposal': proposal, 'goal': goal, 'sources': sources})['artifact']
    save(work / 'original-specification.json', spec)
    save(work / 'proposed-specification.json', revised)
    tests, baseline = prepare(project, work / 'baseline', expected, revised, python)
    old_tests = {t['path']: t['content'].encode('utf-8') for t in spec['tests']}
    edits = materialize_edits(project, expected, candidate['proposal']['edits'], allowed, frozen_tests=old_tests)
    from .feature_workspace import digest
    if {n: digest(b) for n, b in {**old_tests, **edits}.items()} != failed['candidate_hashes']:
        raise ValueError('spec_revision_candidate_bytes_mismatch')
    checked = verify(project, work / 'candidate', expected, tests, edits, revised, baseline, python)
    preservation_outcomes(before, baseline, failed, checked, proposal['corrections'])
    native = {'baseline': execution_feedback(baseline['new_tests']),
              'candidate': execution_feedback(checked), 'unchanged_test_identities': True}
    binding = {'goal': goal, 'source_hashes': expected, 'old_specification': content_digest(spec),
               'new_specification': content_digest(revised), 'candidate_hashes': checked['candidate_hashes'],
               'original_candidate_hashes': failed['candidate_hashes'], 'proposal': content_digest(proposal),
               'native': content_digest(native)}
    revision_digest = content_digest(binding)
    review = q.call([{'role': 'system', 'content': q.policy['spec_dispute_auditor']},
        {'role': 'user', 'content': json.dumps({**payload, 'proposal': proposal,
            'selected_candidate_attempt': ordinal, 'candidate_failure': execution_feedback(failed),
            'revised_specification': revised, 'native_evidence': native,
            'revision_digest': revision_digest}, ensure_ascii=False)}],
        replace(config, provider_label='quality:spec_dispute_auditor'))
    save(work / 'audit.json', review)
    approved = (review.get('decision') == 'approve' and review.get('preserves_goal') is True
                and review.get('revision_digest') == revision_digest and bool(review.get('reason')))
    if inventory(project) != expected:
        raise ValueError('spec_revision_source_changed')
    save(work / 'report.json', {'status': 'revision_qualified' if approved else 'unresolved',
        'binding': binding, 'revision_digest': revision_digest, 'audit': review,
        'grants_product_approval': False, 'old_checkpoint': str(checkpoint)})
    q.record('spec_dispute_reviewed', approved=approved, receipt=str(work / 'report.json'),
             grants_product_approval=False)
    production_proposal = {**candidate['proposal'],
        'edits': [e for e in candidate['proposal']['edits'] if e['path'] not in old_tests]}
    return {'specification': revised, 'proposal': production_proposal,
            'receipt': str(work / 'report.json')} if approved else None
