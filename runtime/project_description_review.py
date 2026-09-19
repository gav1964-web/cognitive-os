"""One optional source lookup round; every draft claim gets a review disposition."""
import json

from .competency_knowledge import invoke_knowledge
from .description_review_tasks import review_tasks


def draft_claims(draft):
    return [{'id': 'purpose', **draft['purpose']},
            *[{'id': f'{key}.{i}', **row} for key in ('scenarios', 'data_flow')
              for i, row in enumerate(draft[key])]]


def review_description(report, instruction, draft, *, root, chat, config, validate, current):
    evidence = report['evidence']
    claims = draft_claims(draft)
    report['review_rounds'] = []
    report['review_audit'] = {'schema_version': 'description_review_audit.v1',
        'status': 'review_not_completed', 'semantic_verified': False, 'automatic_claim_restoration': False,
        'findings': [{'claim_id': row['id'], 'kind': 'review_not_completed', 'matches': []} for row in claims]}
    report['review_tasks'] = review_tasks(report, claims)
    lookup_history = []
    return_flags = None
    extra_instruction = ''
    for round_number in range(2):
        focused = invoke_knowledge('project_description', {'project_root': evidence['root'],
            'action': 'review', 'evidence': evidence, 'claims': claims}, root=root)
        messages = [
            {'role': 'system', 'content': instruction + extra_instruction},
            {'role': 'user', 'content': json.dumps({
                'language': report['language'], 'evidence': focused['evidence'], 'draft': draft,
                'claim_packets': focused['claim_packets'],
                'draft_claims': claims, 'lookup_available': round_number == 0,
                'lookup_history': lookup_history,
                **({'behavior_facts':report['behavior_facts']} if 'behavior_facts' in report else {}),
                **({'return_flag_analysis': return_flags} if return_flags is not None else {}),
                'required_response': 'final_review' if round_number else 'lookup_or_final_review',
                'lookup_limits': {'rounds': 1, 'files': 3, 'characters_per_file': 10000},
            }, ensure_ascii=False)},
        ]
        report['review_request'] = messages
        report['claim_packets'] = focused['claim_packets']
        reviewed = chat(messages, config=config)
        report['review_response'] = reviewed
        report['review_rounds'].append({'request': messages, 'response': reviewed})
        if not current(evidence):
            raise ValueError('description_source_changed_during_request')
        if isinstance(reviewed, dict) and set(reviewed) == {'requests'}:
            if round_number:
                raise ValueError('description_lookup_budget_exhausted')
            requests = reviewed['requests']
            if not isinstance(requests, list) or not 1 <= len(requests) <= 3:
                raise ValueError('description_lookup_count')
            catalog = {row['path']: row for row in evidence.get('source_catalog', [])}
            bound = []
            for item in requests:
                if (not isinstance(item, dict) or set(item) - {'path', 'symbol', 'start_line', 'end_line'}
                        or not isinstance(item.get('path'), str)
                        or ('symbol' in item and not isinstance(item['symbol'], str))
                        or item.get('path') not in catalog):
                    raise ValueError('description_lookup_unknown_source')
                bound.append({**item, 'sha256': catalog[item['path']]['sha256']})
            extra = invoke_knowledge('project_description', {'project_root': evidence['root'],
                                     'action': 'read', 'requests': bound}, root=root)
            # Replace the list, so saved round-zero evidence is not retroactively changed.
            evidence = {**evidence, 'sources': [*evidence['sources'], *extra['evidence']['sources']]}
            lookup_history = [{'request': item, 'source_id': source['id'],
                               'line_start': source['line_start'], 'line_end': source['line_end'],
                               'truncated': source['truncated'],
                               **({'helper_context': source['helper_context']} if 'helper_context' in source else {})}
                              for item, source in zip(requests, extra['evidence']['sources'])]
            report['lookup_history'] = lookup_history
            report['evidence'] = evidence
            selectors = [{k: r[k] for k in ('path', 'sha256', 'symbol')} for r in bound
                         if r.get('symbol') and r['path'].endswith('.py')]
            if selectors:
                facts = invoke_knowledge('project_description', {'project_root': evidence['root'],
                    'action': 'return_flags', 'requests': selectors}, root=root)
                return_flags = facts['return_flag_analysis']
                report['return_flag_analysis'] = return_flags
                extra_instruction = '\n' + facts['instruction']
            continue
        if (not isinstance(reviewed, dict) or set(reviewed) != {'description', 'corrections', 'claim_reviews'}
                or not isinstance(reviewed['corrections'], list)
                or any(not isinstance(item, str) for item in reviewed['corrections'])):
            raise ValueError('description_invalid_review')
        ids = {row['id'] for row in evidence['sources']}
        from .description_shape import normalize_description
        result, shape = normalize_description(reviewed['description'], evidence, root=root)
        result = validate(result, ids)
        report.setdefault('shape_normalization', {})['review'] = shape
        reviews = reviewed['claim_reviews']
        if not isinstance(reviews, list) or len(reviews) != len(claims):
            raise ValueError('description_incomplete_claim_review')
        remaining = {row['id'] for row in claims}
        for row in reviews:
            required = {'claim_id', 'action', 'reason', 'evidence_ids'}
            if (not isinstance(row, dict) or not required <= set(row) or set(row) - required - {'checks'}
                    or not isinstance(row['claim_id'], str) or row['claim_id'] not in remaining
                    or not isinstance(row['action'], str)
                    or row['action'] not in {'retained', 'rephrased', 'removed'}
                    or not isinstance(row['reason'], str) or not row['reason'].strip()
                    or not isinstance(row['evidence_ids'], list)
                    or (not row['evidence_ids'] and row['action'] != 'removed')
                    or any(not isinstance(ref, str) or ref not in ids for ref in row['evidence_ids'])):
                raise ValueError('description_invalid_claim_review')
            remaining.remove(row['claim_id'])
        audited = invoke_knowledge('project_description', {'project_root': evidence['root'],
            'action': 'review', 'evidence': evidence, 'claims': claims, 'reviews': reviews,
            'review_evidence': focused['evidence']}, root=root)
        report['review_audit'] = audited['review_audit']
        report['claim_reviews'] = reviews
        report['unverified_removals'] = [row['claim_id'] for row in reviews
                                        if row['action'] == 'removed' and not row['evidence_ids']]
        originals = {row['id']: row for row in claims}
        report['review_changes'] = [
            {**row, 'draft_text': originals[row['claim_id']]['text'],
             'draft_evidence_ids': originals[row['claim_id']]['evidence_ids'],
             'authority': 'unverified_draft_change'}
            for row in reviews if row['action'] != 'retained']
        report['review_tasks'] = review_tasks(report, claims)
        return result
    raise ValueError('description_review_incomplete')
