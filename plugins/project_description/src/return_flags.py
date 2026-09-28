"""Hash-bound return diagnostics, with conditional witnesses and no source execution."""
import ast
import hashlib
import json

from .helper_context import sections
from .source_lookup import read_requests
from .return_flag_model import check_model
from .scalar_boundary import examples


def _field(node, result):
    if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name)
            and node.value.id == result and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str)):
        return node.slice.value
    return None


def _boolean(node):
    return (isinstance(node, ast.Compare) or
            isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not) or
            isinstance(node, ast.BoolOp) and all(_boolean(v) for v in node.values))


def analyze_function(text, symbol, *, max_predicates=6):
    base = {'symbol': symbol, 'status': 'unsupported', 'semantic_verified': False,
            'scope': 'normal-return suffix under independent Boolean predicate values and ordinary dict operations',
            'full_function_reachability_proven': False, 'source_executed': False}
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return {**base, 'reason': 'incomplete_python_function'}
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == symbol]
    if len(functions) != 1 or len(tree.body) != 1 or functions[0].decorator_list:
        return {**base, 'reason': 'requires_single_undecorated_function'}
    function = functions[0]
    if not isinstance(function.body[-1], ast.Return) or not isinstance(function.body[-1].value, ast.Name):
        return {**base, 'reason': 'requires_terminal_named_result'}
    result = function.body[-1].value.id
    reverse = []
    for node in reversed(function.body[:-1]):
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and (field := _field(node.targets[0], result)) and _boolean(node.value)):
            reverse.append({'kind': 'observe', 'field': field, 'node': node, 'value': node.value})
        elif isinstance(node, ast.If) and not node.orelse and len(node.body) == 1 and isinstance(node.body[0], ast.Raise):
            test, when = node.test, True
            if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
                test, when = test.operand, False
            field = _field(test, result)
            if not field:
                break
            reverse.append({'kind': 'reject', 'field': field, 'when': when, 'node': node})
        else:
            break
    steps, observed, predicates, boundaries = [], set(), {}, {}
    for row in reversed(reverse):
        step = {k: v for k, v in row.items() if k not in ('node', 'value')}
        if row['kind'] == 'observe':
            if row['field'] in observed:
                return {**base, 'reason': 'reassigned_flag_not_supported'}
            # Every evaluation is independent, even if its spelling repeats.
            predicate = f'p{len(predicates)}'
            predicates[predicate] = ast.get_source_segment(text, row['value'])
            boundary = examples(row['value'])
            if boundary is not None:
                boundaries[predicate] = boundary
            step['predicate'] = predicate
            observed.add(row['field'])
        elif row['field'] not in observed:
            return {**base, 'reason': 'guard_depends_on_unmodeled_state'}
        steps.append(step)
    if not steps or not predicates or len(predicates) > max_predicates:
        return {**base, 'reason': 'no_bounded_boolean_suffix'}
    first = reverse[-1]['node'].lineno
    quote = '\n'.join(text.splitlines()[first-1:function.body[-1].end_lineno])
    if len(quote) > 4000:
        return {**base, 'reason': 'suffix_quote_budget'}
    return {**base, 'status': 'modeled', 'prefix_unmodeled': True, 'predicates': predicates,
            'steps': steps, 'suffix_quote': quote, 'integer_boundaries': boundaries,
            'model': check_model(steps, max_predicates=max_predicates),
            'assumptions': ['entry to this suffix is assumed, not proven',
                'predicate values may not be jointly feasible in the full program',
                'ordinary dictionary writes, no overloaded operations or concurrent interference',
                'exceptions during comparisons are outside the normal-return model'],
            'conclusion_limit': 'A false-return witness concerns this suffix only; it is not an executed project counterexample.'}


def analyze_requests(root, requests, collection, policy):
    if not 1 <= len(requests) <= policy['max_functions']:
        raise ValueError('return_flag_request_limit')
    sources = read_requests(root, requests, collection)
    rows = []
    for request, source in zip(requests, sources):
        if not request.get('symbol') or not source['path'].endswith('.py'):
            raise ValueError('return_flag_python_symbol_required')
        spans = [r for r in sections(source['excerpt']) if r['name'] == request['symbol']]
        base = {'path': source['path'], 'sha256': source['sha256'], 'symbol': request['symbol']}
        if (len(spans) != 1 or not spans[0]['complete']
                or source.get('helper_context', {}).get('caller_truncated', True)):
            result = {'status': 'unsupported', 'reason': 'complete_top_level_function_required'}
        else:
            body = spans[0]['text'].split('\n', 1)[1]
            result = analyze_function(body, request['symbol'], max_predicates=policy['max_predicates'])
        row = {**base, **result}
        if len(json.dumps([*rows, row], ensure_ascii=False)) > policy['max_analysis_characters']:
            row = {**base, 'status': 'unsupported', 'reason': 'analysis_character_budget',
                   'source_executed': False, 'semantic_verified': False}
        rows.append(row)
    receipt = {'schema_version': 'return_flag_analysis.v1', 'functions': rows,
               'execution_authorized': False, 'source_executed': False, 'semantic_verified': False}
    receipt['digest'] = hashlib.sha256(json.dumps(receipt, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return receipt
