"""Projects without an existing suite still need native preservation evidence."""
import sys
from pathlib import Path

import pytest

from runtime.feature_acceptance import prepare, validate_spec, specification_feedback, verify
from runtime.feature_workspace import inventory


def specification(preservation=True):
    body = 'from engine import label\ndef test_new():\n    assert label(-2) == "(2)"\n'
    if preservation:
        body += '\ndef test_existing_behavior():\n    assert label(3) == "3"\n'
    return {'tests': [{'path': 'tests/test_labels.py', 'content': body}],
            'regression_tests': [], 'regression_policy': 'new_preservation_only',
            'acceptance': ['parenthesized negative'],
            'limitations': ['newly authored preservation; no existing suite']}


def source(tmp_path):
    root = tmp_path / 'source'
    root.mkdir()
    (root / 'engine.py').write_text('def label(value):\n    return str(value)\n')
    return root


def test_no_existing_suite_still_requires_preservation(tmp_path):
    root = source(tmp_path)
    with pytest.raises(ValueError, match='feature_baseline_not_qualified'):
        prepare(root, tmp_path / 'no-preservation', inventory(root),
                specification(False), Path(sys.executable))


def test_explicit_policy_cannot_skip_an_existing_suite(tmp_path):
    root = source(tmp_path)
    spec = specification()
    with pytest.raises(ValueError, match='feature_existing_regression_required'):
        validate_spec({**spec, 'regression_policy': None}, inventory(root))
    (root / 'test_existing.py').write_text('def test_ok():\n    assert True\n')
    with pytest.raises(ValueError, match='feature_existing_regression_required'):
        validate_spec(spec, inventory(root))


def test_new_preservation_is_frozen_and_must_stay_green(tmp_path):
    root = source(tmp_path)
    expected = inventory(root)
    spec = specification()
    tests, baseline = prepare(root, tmp_path / 'acceptance', expected, spec, Path(sys.executable))
    assert baseline['regression']['tests'] == {}
    assert baseline['regression']['counts']['passed'] == 0
    assert baseline['new_tests']['counts']['passed'] == 1
    assert specification_feedback(baseline)['regression']['failures'] == []
    bad = {'engine.py': b'def label(value):\n    return "(2)"\n'}
    failed = verify(root, tmp_path / 'bad', expected, tests, bad, spec, baseline, Path(sys.executable))
    assert not failed['passed']
    good = {'engine.py': b'def label(value):\n    return f"({-value})" if value < 0 else str(value)\n'}
    passed = verify(root, tmp_path / 'good', expected, tests, good, spec, baseline, Path(sys.executable))
    assert passed['passed'] and passed['counts']['passed'] == 2
    assert inventory(root) == expected
