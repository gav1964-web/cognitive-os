"""Keep executable documentation attached to its original Python symbol."""
import ast
from collections import Counter
import doctest


def doctest_contract(node):
    result = {}
    def visit(current, scope):
        if isinstance(current, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            name = getattr(current, 'name', '<module>')
            scope = (*scope, name)
            examples = doctest.DocTestParser().get_examples(ast.get_docstring(current) or '')
            if examples:
                result[scope] = Counter((e.source, e.want, e.exc_msg,
                    tuple(sorted(e.options.items()))) for e in examples)
        for child in ast.iter_child_nodes(current):
            visit(child, scope)
    visit(node, ())
    return result


def preserves_doctests(original, replacement):
    before, after = doctest_contract(original), doctest_contract(replacement)
    return all(not (examples - after.get(name, Counter())) for name, examples in before.items())
