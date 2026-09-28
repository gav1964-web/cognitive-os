"""Reconsider repeated review routing; never replace review or native acceptance."""
import json
from dataclasses import replace

from .feature_acceptance import save
from .narrow_type_evidence_binding import content_digest


def reconsider_review_owner(q, result, config, default, *, force=False):
    review = result.get('artifacts', {}).get('reviewer', {})
    if review.get('decision') != 'reject':
        return default
    fingerprint = content_digest(review)
    seen = getattr(q, 'seen_rejections', set())
    repeated = fingerprint in seen
    q.seen_rejections = seen | {fingerprint}
    if not force and not repeated:
        return default
    answer = q.call([
        {'role': 'system', 'content': q.policy['repair_router']},
        {'role': 'user', 'content': json.dumps({'review': review,
            'previous_owner': default, 'reason': 'Repeated rejection or resumed rejected review',
            'candidate_tests_passed': bool(result.get('attempts') and result['attempts'][-1].get('passed')),
            'authority': {'architect': 'design', 'spec_writer': 'new acceptance tests; accepted tests immutable',
                          'programmer': 'production code only; cannot edit tests'}}, ensure_ascii=False)}],
        replace(config, provider_label='quality:repair_router'))
    if answer.get('owner') not in ('architect', 'spec_writer', 'programmer') or not answer.get('reason'):
        raise ValueError('quality_repair_route_not_established')
    save(q.work / f'repair-route-{q.cycle}.json', answer)
    q.record('repair_owner_reconsidered', old_owner=default, owner=answer['owner'], reason=answer['reason'])
    return answer['owner']
