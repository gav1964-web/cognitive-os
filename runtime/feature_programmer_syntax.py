"""Bounded model-owned syntax correction before candidate materialization."""
import json
from pathlib import Path

from .feature_acceptance import save
from .feature_workspace import materialize_edits, proposal_for_context


def syntax_feedback(proposal, exc, tests):
    return {'rejected_proposal': proposal_for_context(proposal, tests),
            'syntax_error': {'message': exc.msg, 'line': exc.lineno,
                             'offset': exc.offset, 'text': exc.text},
            'instruction': 'Correct the Python syntax in your production edits. Return the complete proposal against the ORIGINAL source hashes. Frozen tests cannot be changed. No native test or review has approved this proposal.'}


def materialize_with_feedback(*, project, expected, proposal, allowed, tests, ask, work, ordinal):
    for repair in range(2):
        save(work / f'proposal-{ordinal}.json', proposal)
        try:
            edits = materialize_edits(project, expected, proposal['edits'], allowed, frozen_tests=tests)
            return proposal, edits
        except SyntaxError as exc:
            feedback = syntax_feedback(proposal, exc, tests)
            save(work / f'syntax-rejection-{ordinal}-{repair}.json', {
                'proposal': proposal, 'feedback': feedback, 'grants_approval': False})
            if repair:
                raise ValueError('feature_edit_syntax_correction_exhausted') from exc
            proposal = ask('programmer', {'feedback': feedback})


def restored_feedback(checkpoint, project, expected, tests, allowed):
    """Reproduce a saved syntax failure against current bound sources; never repair it."""
    if not checkpoint:
        return None
    checkpoint = Path(checkpoint)
    report = json.loads((checkpoint / 'report.json').read_text(encoding='utf-8'))
    if report.get('attempts') or report.get('status') != 'blocked':
        return None
    if not (report.get('error_type') == 'SyntaxError'
            or report.get('reason') == 'feature_edit_syntax_correction_exhausted'):
        return None
    # Caller validates goal/project/source/roles and native qualification first.
    proposal = json.loads((checkpoint / 'proposal-1.json').read_text(encoding='utf-8'))
    try:
        materialize_edits(project, expected, proposal['edits'], allowed, frozen_tests=tests)
    except SyntaxError as exc:
        if report.get('error_type') == 'SyntaxError' and str(exc) != report.get('reason'):
            raise ValueError('feature_syntax_resume_evidence_changed') from exc
        return syntax_feedback(proposal, exc, tests)
    raise ValueError('feature_syntax_resume_not_reproduced')
