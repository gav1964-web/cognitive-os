"""A stored return can identify a failing call; arbitrary data flow cannot."""
import ast

import pytest

from runtime.repair_target_nomination import trace_failure_methods, nomination_context
from tests.runtime.test_repair_target_nomination import prepare


def test_assigned_return_selects_failing_call_not_previous_success(tmp_path):
    project, packet = prepare(tmp_path, body=
        "    good = render('good')\n    assert good == 'good'\n"
        "    result = render('bad')\n    assert result == 'fixed'\n")
    trace = trace_failure_methods(project=project, packet=packet,
        work_dir=tmp_path / 'trace', authorized=True)
    assert trace['status'] == 'observed_call_scope', trace
    assert nomination_context(project=project, packet=packet, trace=trace)['eligible_targets'] == [
        'core.py:Worker.convert_bad']


@pytest.mark.parametrize('body', [
    "result = render('bad')\nresult = 'broken'\nassert result == 'fixed'",
    "result = render('bad')\nassert observe(result) == 'fixed'",
    "result = render('bad')\nmutate(result)\nassert result == 'fixed'",
    "if enabled:\n    result = render('bad')\nassert result == 'fixed'",
    "result = render('bad') + 'x'\nassert result == 'fixed'",
    "result = render('bad')\ndef inner():\n    return result\nassert result == 'fixed'",
    "result = render('bad'); ignored = render('good')\nassert result == 'fixed'",
    "global result\nresult = render('bad')\nassert result == 'fixed'",
    "result = render('bad')\nassert result == mutate(result)",
    "result = observe(render('bad'))\nassert result == 'fixed'",
    "result = render('bad').strip()\nassert result == 'fixed'",
])
def test_ambiguous_or_transformed_assignments_do_not_expand_scope(body):
    from runtime.repair_target_trace_probe import failing_call_ranges
    tree = ast.parse('def test_case():\n' + '\n'.join('    ' + line for line in body.splitlines()))
    assertion = [n for n in ast.walk(tree) if isinstance(n, ast.Assert)][-1]
    assert failing_call_ranges(tree, assertion.lineno, 'convert') == [(assertion.lineno, assertion.end_lineno)]


def test_two_return_operands_remain_ambiguous(tmp_path):
    project, packet = prepare(tmp_path, body=
        "    left = render('bad')\n    right = render('good')\n    assert left == right\n")
    trace = trace_failure_methods(project=project, packet=packet,
        work_dir=tmp_path / 'trace', authorized=True)
    assert trace['status'] == 'blocked'


def test_multiline_annotated_constructor_result_is_supported():
    from runtime.repair_target_trace_probe import failing_call_ranges
    tree = ast.parse("def test_case():\n    result: str = Worker(\n        'bad'\n    ).convert()\n    assert result == 'fixed'\n")
    assert failing_call_ranges(tree, 5, 'convert') == [(5, 5), (2, 4)]
