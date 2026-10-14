"""Bounded diagnosis abstention; investigation hints never expand edit authority."""
from copy import deepcopy


def with_scope_review(schema: dict) -> dict:
    """Allow a separate response instead of forcing an unsupported repair design."""
    return {'oneOf': [schema, {
        'type': 'object', 'additionalProperties': False,
        'required': ['target', 'failure_signature', 'scope_review'],
        'properties': {
            'target': deepcopy(schema['properties']['target']),
            'failure_signature': deepcopy(schema['properties']['failure_signature']),
            'scope_review': {
                'type': 'object', 'additionalProperties': False,
                'required': ['reason', 'suspected_targets', 'requested_evidence'],
                'properties': {
                    'reason': {'type': 'string', 'minLength': 24, 'maxLength': 2400},
                    'suspected_targets': {'type': 'array', 'maxItems': 4, 'uniqueItems': True,
                        'items': {'type': 'string', 'minLength': 1, 'maxLength': 240}},
                    'requested_evidence': {'type': 'array', 'minItems': 1, 'maxItems': 6,
                        'items': {'type': 'string', 'minLength': 12, 'maxLength': 600}},
                },
            },
        },
    }]}


def validate_scope_review(payload: dict, envelope: dict) -> list[str]:
    from .project_hypothesis_validation import _forbidden_keys
    errors = []
    if set(payload) != {'target', 'failure_signature', 'scope_review'}:
        errors.append('scope_review_response_fields')
    for key in ('target', 'failure_signature'):
        if payload.get(key) != envelope[key]:
            errors.append(key + '_mismatch')
    forbidden = _forbidden_keys(payload)
    if forbidden:
        errors.append('forbidden_fields:' + ','.join(sorted(forbidden)))
    review = payload.get('scope_review')
    if not isinstance(review, dict) or set(review) != {'reason', 'suspected_targets', 'requested_evidence'}:
        return sorted(set(errors + ['scope_review_fields']))
    if not _text(review['reason'], 24, 2400):
        errors.append('scope_review_reason_required')
    for key, minimum, maximum, text_minimum, text_maximum in (
        ('suspected_targets', 0, 4, 1, 240), ('requested_evidence', 1, 6, 12, 600),
    ):
        values = review[key]
        if (not isinstance(values, list) or not minimum <= len(values) <= maximum
                or any(not _text(value, text_minimum, text_maximum) for value in values)):
            errors.append('scope_review_' + key + '_invalid')
        elif key == 'suspected_targets' and len(set(values)) != len(values):
            errors.append('scope_review_suspected_targets_invalid')
    return sorted(set(errors))


def _text(value, minimum, maximum):
    return isinstance(value, str) and minimum <= len(value.strip()) and len(value) <= maximum
