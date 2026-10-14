"""A requested end past EOF is a complete file tail, never an invented range."""
import pytest

from runtime.feature_workspace import inventory, read_sources
from tests.runtime.test_feature_development import project


def test_read_past_eof_returns_actual_lines_and_explicit_end(project):
    rows = read_sources(project, inventory(project), [{'path': 'engine.py', 'start': 1, 'end': 400}])
    assert rows[0]['end'] == rows[0]['total_lines'] == 2
    assert rows[0]['requested_end'] == 400 and rows[0]['eof']
    assert rows[0]['content'] == (project / 'engine.py').read_text()


@pytest.mark.parametrize('start,end', [(0, 2), (3, 4), (2, 1), (1, True)])
def test_invalid_start_or_reversed_range_is_rejected(project, start, end):
    with pytest.raises(ValueError, match='feature_read_range'):
        read_sources(project, inventory(project), [{'path': 'engine.py', 'start': start, 'end': end}])
