"""Detector-oracle branch of the compiled-competency route (learned TRY004/G002 templates)."""
import sys
from pathlib import Path

import pytest

from runtime.feature_competency import run_competency_first
from runtime.fix_template_detector import ruff_executable

try:
    ruff_executable()
except RuntimeError:
    pytest.skip('ruff not installed in this environment', allow_module_level=True)

LEVELS = '''import logging

log = logging.getLogger(__name__)


def set_level(level):
    if not isinstance(level, int):
        raise ValueError("level must be int, not %s" % type(level).__name__)
    log.info("level %s" % level)
    log.debug("pair %s %s" % (level, level))
    return level
'''
REGRESSION = '''import pytest

from pkg.levels import set_level


def test_valid_level():
    assert set_level(3) == 3


def test_invalid_level_is_rejected():
    with pytest.raises(Exception):
        set_level("x")
'''
EXPECTS_VALUE_ERROR = REGRESSION.replace('pytest.raises(Exception)', 'pytest.raises(ValueError)')


def _project(tmp_path, regression=REGRESSION):
    root = tmp_path / 'project'
    (root / 'src/pkg').mkdir(parents=True)
    (root / 'src/pkg/__init__.py').write_text('', encoding='utf-8')
    (root / 'src/pkg/levels.py').write_text(LEVELS, encoding='utf-8')
    if regression:
        (root / 'tests').mkdir()
        (root / 'tests/test_levels.py').write_text(regression, encoding='utf-8')
    return root


def _run(tmp_path, goal, **kwargs):
    return run_competency_first(project=_project(tmp_path, **kwargs), work=tmp_path / 'work',
                                python=Path(sys.executable), goal=goal)


def test_learned_rules_are_fixed_and_detector_verified_without_model_calls(tmp_path):
    report = _run(tmp_path, 'Fix ruff TRY004 and G002 findings in src/pkg/levels.py')
    assert report['status'] == 'verified', report.get('reason')
    assert report['model_calls'] == 0 and report['change']['competency'] == 'learned_fix_templates'
    assert report['detector_check'] == {'sites': 3, 'problems': []}
    assert report['regression']['changed'] == [] and report['regression']['after']['passed'] == 2


def test_behavior_changing_rule_requires_existing_tests(tmp_path):
    report = _run(tmp_path, 'Fix ruff TRY004 in src/pkg/levels.py', regression=None)
    assert report['status'] == 'blocked' and report['reason'] == 'competency_requires_regression_tests'
    preserving = run_competency_first(project=tmp_path / 'project', work=tmp_path / 'work2',
                                      python=Path(sys.executable), goal='Fix ruff G002 in src/pkg/levels.py')
    assert preserving['status'] == 'verified', preserving.get('reason')


def test_changed_exception_type_breaking_a_test_blocks_delivery(tmp_path):
    report = _run(tmp_path, 'Fix ruff TRY004 in src/pkg/levels.py', regression=EXPECTS_VALUE_ERROR)
    assert report['status'] == 'blocked' and report['reason'] == 'competency_regression_outcome_changed'
    assert any(name.endswith('test_invalid_level_is_rejected') for name in report['regression']['changed'])


def test_behavior_change_needs_runnable_referencing_tests(tmp_path):
    collects_nothing = 'from pkg.levels import set_level\n\nHELPER = set_level\n'
    report = _run(tmp_path, 'Fix ruff TRY004 in src/pkg/levels.py', regression=collects_nothing)
    assert report['status'] == 'blocked' and report['reason'] == 'competency_regression_tests_not_runnable'
