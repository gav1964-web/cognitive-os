"""Explicit independent-fragment formatting contract; no project execution."""
import ast


def propose(payload, arguments, limitations):
    fields = ('seed', 'preservation_seed', 'preservation_expected')
    if any(not isinstance(payload.get(key), str) or not 1 <= len(payload[key]) <= 6000 for key in fields):
        raise ValueError('bounded_composition_examples_required')
    seed, control, expected = (payload[key] for key in fields)
    if control == expected:
        raise ValueError('positive_formatting_change_required')
    result = {'status': 'not_applicable', 'contract': payload['contract'], 'tests': [],
        'limitations': limitations, 'source_executed': False, 'source_binding_fields': list(fields)}
    pairs = [(seed, seed), (control, expected),
             (seed + '\n' + control, seed + '\n' + expected),
             (control + '\n' + seed, expected + '\n' + seed)]
    try:
        if any(ast.dump(ast.parse(source)) != ast.dump(ast.parse(output)) for source, output in pairs):
            result['reason'] = 'formatting_examples_change_ast'
            return result
    except SyntaxError:
        result['reason'] = 'composition_not_valid_in_current_python_grammar'
        return result
    for index, (source, output) in enumerate(pairs):
        name = f'test_cos_python_composition_{index}'
        call = payload['function'] + '(source' + (', ' + ', '.join(arguments) if arguments else '') + ')'
        text = (f'def {name}():\n    import ast\n'
            f'    from {payload["module"]} import {payload["function"]}\n'
            f'    source = {source!r}\n    expected = {output!r}\n'
            f'    result = {call}\n    assert result == expected\n'
            '    assert ast.dump(ast.parse(result)) == ast.dump(ast.parse(source))\n')
        result['tests'].append({'name': name, 'source': text, 'input': source,
                               'expected': output, 'input_ast_preserved': True})
        if index == 1:
            result['tests'][-1]['required_baseline_outcome'] = 'passes'
    result.update(status='proposed', variant_count=2)
    return result
