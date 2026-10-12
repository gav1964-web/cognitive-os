"""Output references may reuse exact accepted tests, never author or alter them."""
from copy import deepcopy
from hashlib import sha256


def reference_catalog(frozen):
    return [{'path': row['path'], 'content_reference': 'immutable_previous_tests',
             'content_sha256': sha256(row['content'].encode('utf-8')).hexdigest()}
            for row in frozen]


def repair_reference_metadata(value, frozen):
    """Fill only an omitted digest for an exact, unambiguous accepted reference.

    Never fix a wrong digest/path or accept supplied replacement contents. This
    restores catalog metadata; subsequent expansion and all native gates remain.
    """
    result, changes = deepcopy(value), []
    catalog = reference_catalog(frozen)
    for test in result.get('tests', []):
        if (not isinstance(test, dict) or set(test) != {'path', 'content_reference'}
                or test['content_reference'] != 'immutable_previous_tests'):
            continue
        matches = [row for row in catalog if row['path'] == test['path']]
        if len(matches) == 1:
            test['content_sha256'] = matches[0]['content_sha256']
            changes.append({'path': test['path'], 'field': 'content_sha256',
                            'restored_from': 'immutable_test_refs', 'value': test['content_sha256']})
    return result, changes


def expand_frozen_references(value, frozen, *, allow_separate=False):
    result = deepcopy(value)
    if allow_separate and 'immutable_test_refs' in result:
        refs, tests = result['immutable_test_refs'], result.get('tests', [])
        if (not isinstance(refs, list) or not isinstance(tests, list)
                or any(not isinstance(t, dict) for t in refs + tests)
                or any(set(t) != {'path', 'content_reference', 'content_sha256'} for t in refs)):
            raise ValueError('quality_invalid_frozen_reference')
        paths = [t.get('path') for t in refs + tests]
        if (any(not isinstance(p, str) for p in paths)
                or len(set(paths)) != len(paths)):
            raise ValueError('quality_invalid_frozen_reference')
        result['tests'] = refs + tests
        result.pop('immutable_test_refs')
    bodies = {row['path']: row['content'] for row in frozen}
    if len(bodies) != len(frozen):
        raise ValueError('quality_ambiguous_frozen_reference')
    count = 0
    for test in result.get('tests', []):
        if not isinstance(test, dict) or 'content_reference' not in test:
            continue
        if (set(test) != {'path', 'content_reference', 'content_sha256'}
                or test['content_reference'] != 'immutable_previous_tests'
                or test.get('path') not in bodies):
            raise ValueError('quality_invalid_frozen_reference')
        body = bodies[test['path']]
        if test['content_sha256'] != sha256(body.encode('utf-8')).hexdigest():
            raise ValueError('quality_stale_frozen_reference')
        test.pop('content_reference')
        test.pop('content_sha256')
        test['content'] = body
        count += 1
    return result, count
