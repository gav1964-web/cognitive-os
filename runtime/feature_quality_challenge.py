"""Bounded native feedback to the fault author, without changing the candidate."""
import json
from dataclasses import replace
from pathlib import Path
from plugins.development_quality.src.main import run as quality_contract

from .feature_acceptance import save
from .feature_challenges import check_challenges
from .feature_workspace import inventory
from .narrow_type_evidence_binding import content_digest


def restore_campaign(checkpoint):
    """Retain known fault obligations across a paid-run boundary; reexecute later."""
    checkpoint = Path(checkpoint).resolve()
    journal = checkpoint.parent / 'report.json'
    if not journal.is_file():
        return None, None
    report = json.loads((checkpoint / 'report.json').read_text(encoding='utf-8'))
    prior = json.loads(journal.read_text(encoding='utf-8'))
    source_hashes = json.loads((checkpoint / 'source-inventory.json').read_text(encoding='utf-8'))
    if prior.get('goal') != report['goal'] or prior.get('source_hashes') != source_hashes:
        raise ValueError('quality_campaign_resume_identity')
    index = next((i for i, row in enumerate(prior.get('cycles', []))
                  if Path(row['checkpoint']).resolve() == checkpoint), None)
    if index is None:
        return None, None
    if not report.get('attempts'):
        # An unaccepted spec extension still owes the previous candidate's
        # witnessed faults. Bind/reexecute them later, never treat as approval.
        for row in reversed(prior.get('cycles', [])[:index]):
            earlier = Path(row['checkpoint']).resolve()
            if earlier.parent != checkpoint.parent:
                raise ValueError('quality_campaign_resume_cycle_outside_journal')
            previous = json.loads((earlier / 'report.json').read_text(encoding='utf-8'))
            if previous.get('attempts'):
                return restore_campaign(earlier)
        return None, None
    retained = checkpoint.parent / f'challenges-{index}-retained.json'
    if not retained.is_file():
        return None, None
    from .feature_checkpoint import verified_candidate
    verified = verified_candidate(checkpoint)
    root = checkpoint / f'attempt-{len(report["attempts"])}' / 'project'
    expected = inventory(root)
    if any(expected.get(k) != v for k, v in verified['candidate_hashes'].items()):
        raise ValueError('quality_campaign_resume_candidate_changed')
    saved = json.loads(retained.read_text(encoding='utf-8'))
    if saved.get('candidate_hashes') != expected or not saved.get('challenges'):
        raise ValueError('quality_campaign_resume_binding')
    return {'challenges': saved['challenges']}, {k: v for k, v in expected.items() if not k.startswith('tests/')}


def check_campaign(*, candidate, work, python, specification, allowed, challenges):
    """Recheck the union of two bounded proposals without dropping any variant."""
    candidate, work = Path(candidate).resolve(), Path(work).resolve()
    if not isinstance(challenges, list) or not 1 <= len(challenges) <= 6:
        raise ValueError('quality_campaign_requires_1_to_6_variants')
    if len(challenges) <= 3:
        return check_challenges(candidate=candidate, work=work, python=python,
            specification=specification, allowed=allowed, challenges=challenges)
    expected = inventory(candidate)
    if work.exists() or work.is_relative_to(candidate) or candidate.is_relative_to(work):
        raise ValueError('challenge_fresh_external_workspace_required')
    parts = []
    for offset in range(0, len(challenges), 3):
        checked = check_challenges(candidate=candidate, work=work / str(offset // 3),
            python=python, specification=specification, allowed=allowed,
            challenges=challenges[offset:offset + 3])
        if checked['candidate_hashes'] != expected or not checked['source_unchanged']:
            raise ValueError('quality_challenge_candidate_changed')
        parts.append(checked)
    states = [p['status'] for p in parts]
    status = ('inconclusive' if 'inconclusive' in states else
              'needs_specification' if 'needs_specification' in states else 'passed')
    result = {'status': status, 'candidate_hashes': expected,
              'source_unchanged': inventory(candidate) == expected,
              'variants': [v for p in parts for v in p['variants']]}
    if not result['source_unchanged']:
        result['status'] = 'inconclusive'
    save(work / 'report.json', result)
    return result


def challenge_with_feedback(q, config, payload, *, candidate, work, python, spec, allowed):
    payload = {**payload, 'boundary_probes': quality_contract({
        'action': 'boundary_probes', 'sources': payload.get('candidate_sources', [])})['probes']}
    history, retained = [], []
    expected = inventory(candidate)
    for ordinal in range(2):
        if inventory(candidate) != expected:
            raise ValueError('quality_challenge_candidate_changed')
        proposal = q.call([
            {'role': 'system', 'content': q.policy['challenger']},
            {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)}],
            replace(config, provider_label='quality:challenger'))
        save(work.parent / (work.name + f'-proposal-{ordinal}.json'), proposal)
        try:
            incoming = proposal.get('challenges')
            if not isinstance(incoming, list) or not 1 <= len(incoming) <= 3:
                raise ValueError('challenge_requires_1_to_3_variants')
            if inventory(candidate) != expected:
                raise ValueError('quality_challenge_candidate_changed')
            merged = {content_digest(c): c for c in retained}
            for challenge in incoming:
                merged.setdefault(content_digest(challenge), challenge)
            proposal = {**proposal, 'challenges': list(merged.values())}
            save(work.parent / (work.name + f'-effective-{ordinal}.json'), proposal)
            checked = check_campaign(candidate=candidate, work=work / str(ordinal),
                python=python, specification=spec, allowed=allowed,
                challenges=proposal['challenges'])
        except (ValueError, KeyError, TypeError) as exc:
            checked = {'status': 'inconclusive', 'reason': str(exc), 'variants': []}
        history.append(checked)
        if checked.get('source_unchanged') and checked.get('candidate_hashes') == expected:
            valid = {content_digest(c): c for c in retained}
            for challenge, row in zip(proposal['challenges'], checked['variants']):
                if row['status'] in ('killed', 'survived'):
                    valid.setdefault(content_digest(challenge), challenge)
            retained = list(valid.values())
            save(work.parent / (work.name + '-retained.json'), {
                'candidate_hashes': expected, 'challenges': retained,
                'validation': str(work / str(ordinal) / 'report.json'), 'grants_approval': False})
        if checked['status'] != 'inconclusive':
            break
        feedback = {'reason': checked.get('reason'), 'variants': [
            {k: v for k, v in row.items() if k in ('id', 'status', 'reason_invalid')}
            | {'execution': {name: {
                'counts': row[name]['counts'],
                'output_tail': row[name].get('output_tail', '')[-3000:]}
                for name in ('reference_oracle', 'mutant_oracle', 'acceptance') if name in row}}
            for row in checked['variants']]}
        if ordinal == 0:
            q.record('feedback_routed', owner='challenger', phase='fault_validation', feedback=feedback)
            payload = {**payload, 'previous_proposal': proposal, 'native_feedback': feedback,
                       'retained_valid_challenges': retained,
                       'instruction': 'Correct the invalid fault/witness. Keep the candidate unchanged. Runtime retains all already validated variants; do not replace their obligations.'}
    checked['validation_attempts'] = history[:-1]
    return proposal, checked
