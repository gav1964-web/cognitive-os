import pytest

from runtime.feature_acceptance import validate_spec
from runtime.feature_checkpoint import candidate_matches
from runtime.feature_extension import extension_context
from runtime.feature_workspace import digest
from tests.runtime.test_feature_development import spec


@pytest.mark.parametrize('count', [4, 5, 8, 9])
def test_acceptance_has_room_for_append_only_repairs_but_remains_bounded(count):
    value = spec()
    content = value['tests'][0]['content']
    value['tests'] = [{'path': f'tests/test_extension_{i}.py', 'content': content}
                      for i in range(count)]
    if count > 8:
        with pytest.raises(ValueError, match='feature_test_file_count'):
            validate_spec(value, {'tests/test_existing.py': 'hash'})
    else:
        assert len(validate_spec(value, {'tests/test_existing.py': 'hash'})) == count
        assert extension_context({'spec': value, 'test_hashes': {t['path']: 'hash' for t in value['tests']}})['remaining_test_files'] == 8 - count


@pytest.mark.parametrize('change', ['none', 'source', 'old_test', 'new_source', 'new_test', 'missing'])
def test_extended_candidate_preserves_every_previously_verified_byte(change):
    previous = {'engine.py': 'source', 'tests/test_old.py': 'old'}
    tests = {'tests/test_new.py': b'new test'}
    current = {**previous, 'tests/test_new.py': digest(tests['tests/test_new.py'])}
    if change == 'source':
        current['engine.py'] = 'changed'
    elif change == 'old_test':
        current['tests/test_old.py'] = 'changed'
    elif change == 'new_source':
        current['other.py'] = 'new'
    elif change == 'new_test':
        current['tests/test_new.py'] = 'changed'
    elif change == 'missing':
        del current['engine.py']
    assert candidate_matches(previous, current, tests, allow_test_extension=True) is (change == 'none')
    assert not candidate_matches(previous, current, tests)
