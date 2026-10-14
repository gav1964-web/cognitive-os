"""Pytest subtest labels must retain the replayable parent test identity."""
import pytest

from runtime.project_native_failure_binding import _interpret_pytest_result


@pytest.mark.parametrize('label', ['', '(value=1)', '[simple (unopt)]', '[value=[1, 2]]'])
def test_parent_node_preserved_for_subtest_label(tmp_path, label):
    node = 'tests/test_values.py::TestValues::test_value[parameter with spaces]'
    output = f'E   AssertionError: wrong value\nSUBFAILED{label} {node}\n'
    result = _interpret_pytest_result(tmp_path, 1, output, {})
    assert result['status'] == 'test_failed'
    assert result['failing_nodeids'] == [node]
    assert result['failure_signature']


def test_subtests_deduplicate_parent_but_do_not_bypass_parent_budget(tmp_path):
    def output(count):
        return 'E AssertionError: wrong value\n' + '\n'.join(
            f'SUBFAILED[{label}] tests/test_values.py::test_value_{index}'
            for index in range(count) for label in ['one', 'two'])
    accepted = _interpret_pytest_result(tmp_path, 1, output(8), {})
    rejected = _interpret_pytest_result(tmp_path, 1, output(9), {})
    assert accepted['status'] == 'test_failed' and len(accepted['failing_nodeids']) == 8
    assert rejected['environment_reason'] == 'failure_identity_exceeds_replay_bounds'
    assert rejected['failure_signature'] is None
