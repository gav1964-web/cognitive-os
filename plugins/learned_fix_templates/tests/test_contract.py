"""Registered contract of learned_fix_templates: applicability, template choice, safety."""
from runtime.competency_knowledge import invoke_knowledge

SOURCE = '''import logging
log = logging.getLogger(__name__)


def check(value):
    if not isinstance(value, int):
        raise ValueError("bad %s" % value)
    log.info("one %s" % value)
    log.info("two %s %s" % (value, value))
    log.info("three %s %s %s" % (value, value, value))
    log.info("named %(v)s" % {"v": value})
'''
DIAGS = [{'path': 'pkg/m.py', 'code': 'TRY004', 'row': 7}] + [
    {'path': 'pkg/m.py', 'code': 'G002', 'row': r} for r in (8, 9, 10, 11)]


def _call(goal, diagnostics=DIAGS, path='pkg/m.py'):
    return invoke_knowledge('learned_fix_templates', {
        'operation': 'task_change', 'goal': goal, 'sources': [{'path': path, 'content': SOURCE}],
        'diagnostics': diagnostics})


def test_rules_operation_exposes_provenance_and_evaluation():
    rules = invoke_knowledge('learned_fix_templates', {'operation': 'rules'})['rules']
    assert set(rules) == {'TRY004', 'G002'}
    assert rules['TRY004']['evaluation_leave_one_project_out']['correct'] >= 1
    assert all(t['projects'] >= 2 for row in rules.values() for t in row['templates'])


def test_goal_must_name_a_learned_rule():
    assert _call('Refactor logging setup')['reason'] == 'goal_does_not_request_a_learned_rule'


def test_only_requested_rule_is_changed_and_unsafe_rewrites_are_refused():
    change = _call('Fix G002 lazy logging in pkg/m.py')['change']
    text = change['edits'][0]['content']
    assert "log.info('one %s', value)" in text and "log.info('two %s %s', value, value)" in text
    assert 'raise ValueError' in text  # TRY004 not requested
    assert '"three %s %s %s" % (value, value, value)' in text and '"named %(v)s" % {"v": value}' in text
    assert {s['row'] for s in change['oracle']['sites']} == {8, 9}
    assert change['requires_regression_tests'] is False


def test_behavior_change_is_declared_for_try004():
    change = _call('Fix ruff TRY004')['change']
    assert 'raise TypeError' in change['edits'][0]['content'] and change['requires_regression_tests'] is True


def test_test_files_are_never_edited():
    assert _call('Fix G002', path='tests/test_m.py', diagnostics=[
        {**d, 'path': 'tests/test_m.py'} for d in DIAGS])['status'] == 'not_applicable'
