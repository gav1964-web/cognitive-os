"""Check one explicit keyword invocation in the bounded pure Python model.

Omitted defaults are not a promise that an API accepts them. Unknown calls stay
unknown; this analysis never executes source or assumes backend behavior.
"""
import ast
from copy import deepcopy

from .return_paths import Unsupported, Raised, _validate, _invoke


def analyze_inputs(text, symbol, inputs, *, success=None):
    result = {'schema_version': 'api_input_analysis.v1', 'status': 'unknown',
              'scope': 'one_explicit_keyword_invocation', 'symbol': symbol,
              'inputs': deepcopy(inputs), 'source_executed': False,
              'semantic_verified': False, 'complete': False,
              'assumptions': ['ordinary Boolean/None inputs and owned dictionaries',
                              'no monkeypatching, concurrency or overloaded operations']}
    if success is not None:
        result['success_condition'] = deepcopy(success)
    try:
        if success is not None and (not isinstance(success, dict) or set(success) != {'field', 'expected'}
                or not isinstance(success['field'], str) or not 0 < len(success['field']) <= 100
                or type(success['expected']) not in (bool, str, type(None))
                or (isinstance(success['expected'], str) and len(success['expected']) > 100)):
            raise Unsupported('invalid_success_condition')
        if (not isinstance(inputs, dict) or len(inputs) > 6
                or any(not isinstance(k, str) or not k.isidentifier()
                       or type(v) not in (bool, type(None)) for k, v in inputs.items())):
            raise Unsupported('invalid_keyword_inputs')
        tree = ast.parse(text)
        if not tree.body or any(not isinstance(n, ast.FunctionDef) for n in tree.body):
            raise Unsupported('complete_function_definitions_required')
        functions = {n.name: n for n in tree.body}
        if len(functions) != len(tree.body) or symbol not in functions or len(functions) > 7:
            raise Unsupported('function_identity_or_count')
        function = functions[symbol]
        args = function.args
        if args.posonlyargs or args.vararg or args.kwarg or function.decorator_list:
            raise Unsupported('unsupported_keyword_signature')
        names = [a.arg for a in [*args.args, *args.kwonlyargs]]
        if len(names) > 6 or len(names) != len(set(names)):
            raise Unsupported('parameter_budget_or_duplicates')
        defaults = {}
        pairs = list(zip(args.args[len(args.args)-len(args.defaults):], args.defaults))
        pairs += list(zip(args.kwonlyargs, args.kw_defaults))
        for parameter, value in pairs:
            if value is None:  # Required keyword-only parameter.
                continue
            if not isinstance(value, ast.Constant) or type(value.value) not in (bool, type(None)):
                raise Unsupported('non_literal_default')
            defaults[parameter.arg] = value.value
        if set(inputs) - set(names) or set(names) - (set(defaults) | set(inputs)):
            result.update(status='counterexample_in_model', complete=True, outcome='argument_binding_error')
            return result
        bound = {**defaults, **inputs}
        # Binding is complete; the existing evaluator receives a full environment.
        args.args += args.kwonlyargs
        args.kwonlyargs, args.defaults, args.kw_defaults = [], [], []
        for item in functions.values():
            _validate(item, functions)
        result['bound_inputs'] = bound.copy()
        try:
            value, _ = _invoke(function, bound, functions, [symbol])
        except Raised:
            result.update(status='counterexample_in_model', complete=True, outcome='raises')
        else:
            result.update(status='holds_in_model', complete=True, outcome='normal_return')
            if success is not None:
                field, expected = success['field'], success['expected']
                present = type(value) is dict and field in value
                matched = present and type(value[field]) is type(expected) and value[field] == expected
                result.update(status='holds_in_model' if matched else 'counterexample_in_model',
                              field_present=present, field_matches=bool(matched))
    except (Unsupported, SyntaxError, ValueError, RecursionError) as exc:
        result['reason'] = str(exc)[:160]
    return result
