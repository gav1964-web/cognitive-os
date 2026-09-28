"""Bounded native feedback to the fault author, without changing the candidate."""
import json
from dataclasses import replace
from plugins.development_quality.src.main import run as quality_contract

from .feature_acceptance import save
from .feature_challenges import check_challenges


def challenge_with_feedback(q, config, payload, *, candidate, work, python, spec, allowed):
    payload = {**payload, 'boundary_probes': quality_contract({
        'action': 'boundary_probes', 'sources': payload.get('candidate_sources', [])})['probes']}
    history = []
    for ordinal in range(2):
        proposal = q.call([
            {'role': 'system', 'content': q.policy['challenger']},
            {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)}],
            replace(config, provider_label='quality:challenger'))
        save(work.parent / (work.name + f'-proposal-{ordinal}.json'), proposal)
        try:
            checked = check_challenges(candidate=candidate, work=work / str(ordinal),
                python=python, specification=spec, allowed=allowed,
                challenges=proposal.get('challenges'))
        except (ValueError, KeyError, TypeError) as exc:
            checked = {'status': 'inconclusive', 'reason': str(exc), 'variants': []}
        history.append(checked)
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
                       'instruction': 'Correct the invalid fault/witness. Keep the candidate unchanged.'}
    checked['validation_attempts'] = history[:-1]
    return proposal, checked
