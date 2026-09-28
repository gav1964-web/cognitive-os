"""Exception type mismatches need production provenance, not just a crash."""
import sys
from pathlib import Path

import pytest

from runtime.feature_acceptance import probe
from runtime.feature_challenges import assertion_failure


@pytest.mark.parametrize('implementation,body,expected', [
    ('return row["value"]', 'with pytest.raises(ValueError):\n        normalize(None)', True),
    ('return row["value"]', 'with pytest.raises(ValueError):\n        normalize({})', True),
    ('return row["value"]', 'normalize(None)', False),
    ('return row["value"]', 'with pytest.raises(ValueError):\n        normalize(int(None))', False),
    ('import missing_dependency', 'with pytest.raises(ValueError):\n        normalize(None)', False),
    ('return undefined_name', 'with pytest.raises(ValueError):\n        normalize(None)', False),
    ('return row["value"]', 'with pytest.raises(ValueError):\n        int(None)', False),
])
def test_production_exception_contract(tmp_path, implementation, body, expected):
    root = tmp_path / 'source'
    (root / 'tests').mkdir(parents=True)
    (root / 'engine.py').write_text('def normalize(row):\n    ' + implementation + '\n')
    (root / 'tests/test_contract.py').write_text(
        'import pytest\nfrom engine import normalize\n'
        'class TestContract:\n    def test_expected(self):\n        '
        + body.replace('\n', '\n    ') + '\n')
    result = probe(root, tmp_path / 'check', Path(sys.executable), ['tests'], {})
    assert assertion_failure(result) is expected, result
    assert result['source_unchanged']
