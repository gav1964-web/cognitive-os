"""Invalid data fixtures must not hide actual source or test damage."""
import pytest
from plugins.project_map_report.src.source_health import source_health


def health(paths, **extra):
    return source_health({}, {}, {}, {'skipped': [
        {'path': p, 'reason': 'SyntaxError'} for p in paths]}, extra)


def test_all_fixture_errors_classified_before_sample_truncation():
    result = health([f'testing/data/invalid{i}.py' for i in range(20)])
    assert result['status'] == 'noisy'
    assert result['test_data_syntax_error_count'] == 20
    assert len(result['test_data_syntax_error_samples']) == 12
    assert result['syntax_error_count'] == 0


@pytest.mark.parametrize('path', ['src/data/broken.py', 'src/fixtures/broken.py',
    'tests/test_broken.py', 'tests/conftest.py', 'tests/data/../../app.py', '/tests/data/a.py',
    'C:/tests/data/a.py', 'testing/database/a.py'])
def test_unknown_production_and_executable_tests_remain_damaged(path):
    result = health(['tests/data/example.py', path])
    assert result['status'] == 'damaged'
    assert result['syntax_error_count'] == 1
    assert result['test_data_syntax_error_count'] == 1


def test_inaccessible_source_still_blocks_with_only_fixture_syntax():
    result = health(['tests/data/input.py'], skipped=[{'path':'src/main.py','reason':'OSError'}])
    assert result['status'] == 'damaged'
    assert result['inaccessible_count'] == 1
