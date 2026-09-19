"""Exact nearby integer examples for a single parameter-to-integer comparison."""
import ast
import operator

OPS = {ast.Lt: operator.lt, ast.LtE: operator.le, ast.Gt: operator.gt,
       ast.GtE: operator.ge, ast.Eq: operator.eq, ast.NotEq: operator.ne}


def examples(node):
    if (not isinstance(node, ast.Compare) or len(node.ops) != 1
            or not isinstance(node.left, ast.Name) or len(node.comparators) != 1
            or not isinstance(node.comparators[0], ast.Constant)):
        return None
    bound = node.comparators[0].value
    operation = OPS.get(type(node.ops[0]))
    if type(bound) is not int or abs(bound) > 10**9 or operation is None:
        return None
    return {'operand': node.left.id, 'boundary': bound,
            'cases': [{'value': value, 'predicate_result': operation(value, bound)}
                      for value in (bound-1, bound, bound+1)],
            'scope': 'this expression with ordinary integer operands only; not an executed function',
            'full_function_reachability_proven': False}
