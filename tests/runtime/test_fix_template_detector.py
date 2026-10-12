"""Detector anchoring with ruff: resolved diagnostics, localisation and verification."""
import ast

import pytest

from runtime.fix_template_mining import statement_pairs

detector = pytest.importorskip('runtime.fix_template_detector')
try:
    detector.ruff_executable()
except RuntimeError:
    pytest.skip('ruff not installed in this environment', allow_module_level=True)

BEFORE = 'def f(x):\n    if x == None:\n        return 1\n    return 2\n'
AFTER = 'def f(x):\n    if x is None:\n        return 1\n    return 2\n'


def _diags(tmp_path, text, name):
    folder = tmp_path / name
    folder.mkdir()
    (folder / 'm.py').write_text(text, encoding='utf-8')
    return detector.run_ruff(folder, select='E711', ignore='').get('m.py', [])


def test_edit_resolving_a_diagnostic_is_anchored_to_its_rule(tmp_path):
    before, after = _diags(tmp_path, BEFORE, 'a'), _diags(tmp_path, AFTER, 'b')
    assert [d['code'] for d in before] == ['E711'] and after == []
    anchored = list(detector.anchor(statement_pairs(BEFORE, AFTER), before, after))
    assert [(ast.unparse(b).splitlines()[0], rule) for b, a, rule, fixable in anchored] == [('if x == None:', 'E711')]


def test_rule_sites_and_detector_verification(tmp_path):
    source = 'value = compute()\nflag = value == None\n'
    diags = _diags(tmp_path, source, 'c')
    [node] = detector.statements_with_rule(source, diags, 'E711')
    good = detector.replace_statement(source, node, 'flag = value is None')
    bad = detector.replace_statement(source, node, 'flag = value == None')
    assert detector.detector_verified(source, good, node, 'E711', tmp_path / 'v1')
    assert not detector.detector_verified(source, bad, node, 'E711', tmp_path / 'v2')
