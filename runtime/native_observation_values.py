"""Bounded Python state projections; never call repr, properties or user hooks."""
import ast
import functools
import types

try:
    from .repair_observation_probe import safe_value
    from .repair_target_trace_probe import code_digest
except ImportError:
    from repair_observation_probe import safe_value
    from repair_target_trace_probe import code_digest

AST_TYPES = frozenset(v for v in vars(ast).values() if isinstance(v, type) and issubclass(v, ast.AST))


def state_value(value, callables, depth=0):
    kind = type(value)
    if kind in AST_TYPES:
        # Exact standard AST classes only. Fields come from instance storage, not descriptors.
        fields = object.__getattribute__(value, '__dict__')
        result = {'type': 'ast.' + kind.__name__}
        for key in ('lineno', 'col_offset', 'end_lineno', 'end_col_offset'):
            if type(fields.get(key)) is int:
                result[key] = fields[key]
        if depth < 2:
            result['fields'] = {name: state_value(fields[name], callables, depth + 1)
                               for name in kind._fields[:12] if name in fields}
        else:
            result['fields_omitted'] = True
        return result
    if kind in (list, tuple):
        result = {'type': kind.__name__, 'length': len(value)}
        if depth < 3:
            result['items'] = [state_value(v, callables, depth + 1) for v in value[:3]]
            result['omitted_items'] = max(0, len(value) - 3)
        else:
            result['items_omitted'] = True
        return result
    if kind is types.FunctionType:
        code = value.__code__
        row = callables.get((code.co_filename, code.co_name))
        if row and code_digest(code) == row['code_digest']:
            return {'type': 'source_function', 'target': row['target'], 'code_digest': row['code_digest']}
        return {'type': 'unverified_function', 'value_omitted': True}
    if kind is functools.partial:
        if depth >= 3 or len(value.args) > 4 or len(value.keywords) > 8:
            return {'type': 'partial', 'value_omitted': True}
        return {'type': 'partial', 'function': state_value(value.func, callables, depth + 1),
                'args': state_value(value.args, callables, depth + 1),
                'keywords': {k: state_value(v, callables, depth + 1) for k, v in value.keywords.items()}}
    return safe_value(value)
