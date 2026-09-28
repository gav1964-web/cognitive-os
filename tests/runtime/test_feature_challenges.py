import sys
from pathlib import Path

import pytest

from runtime.feature_challenges import check_challenges
from runtime.feature_workspace import digest


@pytest.mark.parametrize('strong,broken_oracle', [(False, False), (True, False), (False, True)])
def test_only_proven_faults_count_as_survivors_or_kills(tmp_path, strong, broken_oracle):
    root = tmp_path / 'candidate'
    (root / 'tests').mkdir(parents=True)
    source = 'def label(value):\n    return f"({-value})" if value < 0 else str(value)\n'
    (root / 'engine.py').write_text(source)
    test = 'from engine import label\ndef test_old():\n    assert label(3) == "3"\n'
    if strong:
        test += 'def test_new():\n    assert label(-2) == "(2)"\n'
    (root / 'tests/test_acceptance.py').write_text(test)
    oracle = ('from missing_module import label\n' if broken_oracle else 'from engine import label\n')
    oracle += 'def test_witness():\n    assert label(-2) == "(2)"\n'
    challenge = {'id': 'negative', 'reason': 'negative formatting lost', 'edits': [
        {'path': 'engine.py', 'source_sha256': digest((root / 'engine.py').read_bytes()),
         'replacements': [{'old': source, 'new': 'def label(value):\n    return str(value)\n'}]}],
        'oracle_tests': [{'path': 'tests/test_witness.py', 'content': oracle}]}
    result = check_challenges(candidate=root, work=tmp_path / 'challenge', python=Path(sys.executable),
        specification={'tests': [{'path': 'tests/test_acceptance.py'}], 'regression_tests': []},
        allowed=['engine.py'], challenges=[challenge])
    expected = 'invalid' if broken_oracle else 'killed' if strong else 'survived'
    assert result['variants'][0]['status'] == expected, result
    assert result['source_unchanged']


@pytest.mark.parametrize('body,expected', [
    ('with pytest.raises(ValueError):\n        int("12")', True),
    ('with pytest.raises(ValueError):\n        int(None)', False),
    ('raise RuntimeError("broken fixture")', False),
])
def test_missing_expected_exception_is_assertion_but_wrong_exception_is_not(tmp_path, body, expected):
    from runtime.feature_acceptance import probe
    from runtime.feature_challenges import assertion_failure
    root=tmp_path/'source';(root/'tests').mkdir(parents=True)
    (root/'tests/test_contract.py').write_text('import pytest\ndef test_error_contract():\n    '+body+'\n')
    result=probe(root,tmp_path/'check',Path(sys.executable),['tests'],{})
    assert assertion_failure(result) is expected
