"""Reviewer edge cases frozen before code generation, not sent as repair hints."""
import ast

import pytest

from runtime.failure_test_context import test_support_context


@pytest.mark.parametrize('binding', [
    'obj.flag, helper = False, None',
    'obj[index], helper = False, None',
    'obj.flag, [other, *helper] = False, [1, 2]',
    'obj.flag = helper = None',
])
def test_mixed_mutation_preserves_actual_rebinding(binding):
    source = 'def helper(): return 7\n' + binding + '\ndef test_case(): assert helper()\n'
    tree = ast.parse(source)
    result = test_support_context(source, tree, tree.body[-1])
    assert result['ambiguous_names'] == ['helper']
    assert result['sources'] == []


def test_same_name_repeated_in_one_assignment_is_not_a_second_definition():
    source = 'helper, helper = 1, 2\ndef test_case(): assert helper\n'
    tree = ast.parse(source)
    result = test_support_context(source, tree, tree.body[-1])
    # Outside current repair acceptance: existing behavior is conservative;
    # keep that behavior rather than silently broadening this stage.
    assert result['ambiguous_names'] == ['helper']
