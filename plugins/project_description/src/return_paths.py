"""Finite normal-return checking for explicit properties of small pure functions.

Never execute source. Unsupported syntax stops the proof, including dead syntax.
Results concern Boolean/None inputs and owned dicts, not arbitrary Python.
"""
import ast
from itertools import product


class Unsupported(ValueError):
    pass


class Returned(Exception):
    def __init__(self, value, line):
        self.value, self.line = value, line


class Raised(Exception):
    def __init__(self, kind):
        self.kind = kind


EXCEPTIONS = {'ValueError', 'RuntimeError', 'TypeError'}


def _caught_types(handler):
    if handler.name:
        raise Unsupported('exception_binding')
    if handler.type is None:
        return EXCEPTIONS
    nodes = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    if not nodes or any(not isinstance(n, ast.Name) or n.id not in EXCEPTIONS for n in nodes):
        raise Unsupported('unknown_exception_handler')
    return {n.id for n in nodes}


def _args(function):
    args = function.args
    if (args.vararg or args.kwarg or args.defaults or args.kw_defaults
            or args.kwonlyargs or function.decorator_list):
        raise Unsupported('unsupported_signature')
    names = [a.arg for a in [*args.posonlyargs, *args.args]]
    if len(names) != len(set(names)):
        raise Unsupported('duplicate_parameter')
    return names


def _validate(function, functions):
    if set(_args(function)).intersection(functions):
        raise Unsupported('shadowed_function')
    if len(list(ast.walk(function))) > 300:
        raise Unsupported('function_node_budget')
    allowed = (ast.FunctionDef, ast.arguments, ast.arg, ast.Assign, ast.AnnAssign,
               ast.If, ast.Return, ast.Raise, ast.Pass, ast.Expr, ast.Constant,
               ast.Name, ast.Load, ast.Store, ast.Dict, ast.Subscript, ast.UnaryOp,
               ast.Not, ast.BoolOp, ast.And, ast.Or, ast.Compare, ast.Eq, ast.NotEq,
               ast.Is, ast.IsNot, ast.Call, ast.keyword, ast.Try, ast.ExceptHandler, ast.Tuple)
    for node in ast.walk(function):
        if not isinstance(node, allowed):
            raise Unsupported('unsupported_syntax:' + type(node).__name__)
        if isinstance(node, ast.FunctionDef) and node is not function:
            raise Unsupported('nested_function')
        if isinstance(node, ast.ExceptHandler):
            _caught_types(node)
        if isinstance(node, ast.Raise) and (node.cause is not None
                or not isinstance(node.exc, ast.Call) or not isinstance(node.exc.func, ast.Name)
                or node.exc.func.id not in EXCEPTIONS or node.exc.keywords
                or len(node.exc.args) > 1
                or any(not isinstance(a, ast.Constant) or type(a.value) is not str for a in node.exc.args)):
            raise Unsupported('unsupported_raise')
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id in EXCEPTIONS:
            raise Unsupported('shadowed_exception')
        if isinstance(node, ast.Call) and (not isinstance(node.func, ast.Name)
                or node.func.id not in {*functions, 'ValueError', 'RuntimeError', 'TypeError'}):
            raise Unsupported('unknown_call')
        if isinstance(node, ast.Assign) and len(node.targets) != 1:
            raise Unsupported('multiple_assignment')
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id in functions:
            raise Unsupported('shadowed_function')
        if isinstance(node, ast.Dict) and any(k is None for k in node.keys):
            raise Unsupported('dictionary_unpack')


def _value(node, env, functions, stack):
    if isinstance(node, ast.Constant) and type(node.value) in (bool, str, type(None)):
        return node.value
    if isinstance(node, ast.Name) and node.id in env:
        return env[node.id]
    if isinstance(node, ast.Dict):
        keys = [_value(k, env, functions, stack) for k in node.keys]
        if any(type(k) is not str for k in keys):
            raise Unsupported('non_string_dictionary_key')
        return {k: _value(v, env, functions, stack) for k, v in zip(keys, node.values)}
    if isinstance(node, ast.Subscript):
        obj = _value(node.value, env, functions, stack)
        key = _value(node.slice, env, functions, stack)
        if type(obj) is not dict or type(key) is not str or key not in obj:
            raise Unsupported('unresolved_field_read')
        return obj[key]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not _truth(_value(node.operand, env, functions, stack))
    if isinstance(node, ast.BoolOp):
        for operand in node.values:
            value = _value(operand, env, functions, stack)
            truth = _truth(value)
            if isinstance(node.op, ast.And) and not truth:
                return value
            if isinstance(node.op, ast.Or) and truth:
                return value
        return value
    if isinstance(node, ast.Compare):
        left = _value(node.left, env, functions, stack)
        for op, expression in zip(node.ops, node.comparators):
            right = _value(expression, env, functions, stack)
            if any(type(v) not in (bool, type(None)) for v in (left, right)):
                raise Unsupported('non_boolean_or_none_comparison')
            matched = (left == right) if isinstance(op, (ast.Eq, ast.Is)) else (left != right)
            if not matched:
                return False
            left = right
        return True
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in functions:
        if node.func.id in env:
            raise Unsupported('shadowed_function')
        function = functions[node.func.id]
        if function.name in stack or len(stack) >= 4:
            raise Unsupported('call_depth_or_recursion')
        names = _args(function)
        values = [_value(v, env, functions, stack) for v in node.args]
        if len(values) > len(names) or any(k.arg is None for k in node.keywords):
            raise Unsupported('call_arguments')
        local = dict(zip(names, values))
        for keyword in node.keywords:
            if (keyword.arg not in names or keyword.arg in local
                    or keyword.arg in [a.arg for a in function.args.posonlyargs]):
                raise Unsupported('call_arguments')
            local[keyword.arg] = _value(keyword.value, env, functions, stack)
        if set(local) != set(names):
            raise Unsupported('call_arguments')
        value, _line = _invoke(function, local, functions, [*stack, function.name])
        return value
    raise Unsupported('unsupported_expression:' + type(node).__name__)


def _truth(value):
    if type(value) not in (bool, type(None)):
        raise Unsupported('non_boolean_condition')
    return bool(value)


def _block(body, env, functions, stack):
    for node in body:
        if isinstance(node, ast.Return):
            raise Returned(_value(node.value, env, functions, stack) if node.value else None, node.lineno)
        if isinstance(node, ast.Raise):
            if node.exc.func.id in env or node.exc.func.id in functions:
                raise Unsupported('shadowed_exception')
            raise Raised(node.exc.func.id)
        if isinstance(node, ast.If):
            branch = node.body if _truth(_value(node.test, env, functions, stack)) else node.orelse
            _block(branch, env, functions, stack)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            if node.value is None:
                raise Unsupported('uninitialized_annotation')
            value = _value(node.value, env, functions, stack)
            target = node.targets[0] if isinstance(node, ast.Assign) else node.target
            if isinstance(target, ast.Name):
                env[target.id] = value
            elif isinstance(target, ast.Subscript):
                obj = _value(target.value, env, functions, stack)
                key = _value(target.slice, env, functions, stack)
                if type(obj) is not dict or type(key) is not str:
                    raise Unsupported('unresolved_field_write')
                obj[key] = value
            else:
                raise Unsupported('assignment_target')
        elif isinstance(node, ast.Expr):
            if isinstance(node.value, ast.Call):
                _value(node.value, env, functions, stack)
            elif not isinstance(node.value, ast.Constant) or not isinstance(node.value.value, str):
                raise Unsupported('expression_statement')
        elif isinstance(node, ast.Try):
            try:
                try:
                    _block(node.body, env, functions, stack)
                except Raised as exc:
                    for handler in node.handlers:
                        kinds = _caught_types(handler)
                        if any(name in env or name in functions for name in kinds):
                            raise Unsupported('shadowed_exception')
                        if exc.kind in kinds:
                            _block(handler.body, env, functions, stack)
                            break
                    else:
                        raise
                else:
                    _block(node.orelse, env, functions, stack)
            except Unsupported:
                # An unmodeled operation is not a Python exception or a proven
                # terminating path; a finally return cannot certify it away.
                raise
            except (Returned, Raised):
                _block(node.finalbody, env, functions, stack)
                raise
            else:
                _block(node.finalbody, env, functions, stack)
        elif not isinstance(node, (ast.If, ast.Pass)):
            raise Unsupported('unsupported_statement:' + type(node).__name__)


def _invoke(function, env, functions, stack):
    try:
        _block(function.body, env, functions, stack)
    except Returned as result:
        return result.value, result.line
    return None, function.end_lineno


def analyze(text, symbol, field, *, max_inputs=6, max_cases=64):
    result = {'schema_version': 'normal_return_analysis.v1', 'status': 'unknown',
              'symbol': symbol, 'field': field, 'scope': 'every_normal_return',
              'input_domain': 'all False/True/None combinations of positional parameters',
              'source_executed': False, 'semantic_verified': False,
              'assumptions': ['ordinary Python Boolean/None values and owned dictionaries',
                              'no monkeypatching, concurrent mutation or overloaded operations'],
              'normal_returns': [], 'raised_inputs': [], 'complete': False}
    try:
        tree = ast.parse(text)
        if not tree.body or any(not isinstance(n, ast.FunctionDef) for n in tree.body):
            raise Unsupported('complete_function_definitions_required')
        functions = {n.name: n for n in tree.body}
        if len(functions) != len(tree.body) or symbol not in functions or len(functions) > 7:
            raise Unsupported('function_identity_or_count')
        # Validate all supplied bodies before exploring paths: unvisited unsupported
        # code is not silently interpreted as evidence of completeness.
        for function in functions.values():
            _validate(function, functions)
        names = _args(functions[symbol])
        if len(names) > max_inputs or 3 ** len(names) > max_cases:
            raise Unsupported('input_budget')
        for values in product((False, True, None), repeat=len(names)):
            arguments = dict(zip(names, values))
            try:
                returned, line = _invoke(functions[symbol], dict(arguments), functions, [symbol])
            except Raised:
                result['raised_inputs'].append(arguments)
                continue
            value = returned.get(field) if type(returned) is dict else None
            result['normal_returns'].append({'inputs': arguments, 'line': line,
                'field_present': type(returned) is dict and field in returned,
                'field_is_true': value is True})
        rows = result['normal_returns']
        result.update(complete=True, status='holds_in_model' if rows and all(r['field_is_true'] for r in rows)
                      else 'counterexample_in_model' if rows else 'no_normal_returns')
    except (Unsupported, SyntaxError, ValueError, RecursionError) as exc:
        result['reason'] = str(exc)[:160]
    return result
