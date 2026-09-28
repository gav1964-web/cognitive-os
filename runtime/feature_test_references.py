"""Lossless prompt references for repeated complete test bodies; never source filtering."""
from copy import deepcopy


CANONICAL = ('immutable_previous_tests', 'specification.tests')
TARGETS = ('quality_contract_feedback.rejected.tests',
           'quality_contract_feedback.incomplete_correction.tests',
           'artifacts.spec_writer.tests', 'previous_unaccepted_draft.rejected.tests',
           'previous_unaccepted_draft.incomplete_correction.tests')
CONTRACT = 'same_path_exact_test_content.v1'


def _get(value, path):
    for key in path.split('.'):
        value = value.get(key) if isinstance(value, dict) else None
    return value


def _bodies(payload, field):
    rows = _get(payload, field)
    if not isinstance(rows, list):
        return {}
    names = [r.get('path') for r in rows if isinstance(r, dict)]
    return {r['path']: r['content'] for r in rows if isinstance(r, dict)
            and isinstance(r.get('path'), str) and names.count(r['path']) == 1
            and isinstance(r.get('content'), str)}


def expand_test_references(payload):
    result = deepcopy(payload)
    if result.pop('test_reference_contract', None) != CONTRACT:
        raise ValueError('feature_test_reference_contract')
    canonical = {field: _bodies(result, field) for field in CANONICAL}
    for path in TARGETS:
        for test in _get(result, path) or []:
            if not isinstance(test, dict) or 'content_reference' not in test:
                continue
            field = test.pop('content_reference')
            if 'content' in test or field not in canonical or test.get('path') not in canonical[field]:
                raise ValueError('feature_test_reference_unresolved')
            test['content'] = canonical[field][test['path']]
    return result


def compact_test_references(payload):
    if not isinstance(payload, dict) or 'test_reference_contract' in payload:
        return payload, 0
    result, count = deepcopy(payload), 0
    canonical = {field: _bodies(result, field) for field in CANONICAL}
    for path in TARGETS:
        rows = _get(result, path)
        if not isinstance(rows, list):
            continue
        for test in rows:
            if not isinstance(test, dict) or 'content_reference' in test:
                continue
            body = test.get('content')
            if not isinstance(body, str) or len(body) < 512:
                continue
            for field, bodies in canonical.items():
                if bodies.get(test.get('path')) == body:
                    test.pop('content')
                    test['content_reference'] = field
                    count += 1
                    break
    if count:
        result['test_reference_contract'] = CONTRACT
        if expand_test_references(result) != payload:
            raise ValueError('feature_test_reference_not_lossless')
    return result, count
