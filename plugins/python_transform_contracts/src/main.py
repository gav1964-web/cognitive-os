"""Pure bounded property generation; no project imports or execution."""
import ast
import io
import json
import keyword
import tokenize
from pathlib import Path


def _identifier(value):
    return isinstance(value, str) and value.isidentifier() and not keyword.iskeyword(value)


def variants(source, maximum=6):
    """Vary bracket layout only when the complete input AST stays identical."""
    tree = ast.dump(ast.parse(source), include_attributes=False)
    lines = source.splitlines(keepends=True)
    offsets, offset = [], 0
    for line in lines:
        offsets.append(offset)
        offset += len(line)
    tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    stack, pairs = [], []
    for token in tokens:
        if token.type != tokenize.OP:
            continue
        if token.string in '([{':
            stack.append(token)
        elif token.string in ')]}' and stack:
            pairs.append((stack.pop(), token))
    rows = [source]
    for opening, closing in pairs:
        start = offsets[opening.end[0]-1] + opening.end[1]
        end = offsets[closing.start[0]-1] + closing.start[1]
        indent = lines[opening.start[0]-1]
        indent = indent[:len(indent)-len(indent.lstrip())]
        for insertion in ('\n', '  # acceptance layout variant\n'):
            candidate = source[:start] + insertion + indent + '    ' + source[start:end] + '\n' + indent + source[end:]
            try:
                equivalent = ast.dump(ast.parse(candidate), include_attributes=False) == tree
            except SyntaxError:
                continue
            if equivalent and candidate not in rows:
                rows.append(candidate)
                if len(rows) == maximum:
                    return rows
    return rows


def run(payload):
    policy = json.loads((Path(__file__).resolve().parents[1]/'knowledge/properties.json').read_text(encoding='utf-8'))
    if payload['operation'] != 'acceptance_tests' or payload['contract'] not in (policy['contract'],policy['formatting_contract']):
        raise ValueError('unsupported_transform_contract')
    module, function = payload['module'], payload['function']
    if not isinstance(module, str) or not all(_identifier(part) for part in module.split('.')) or not _identifier(function):
        raise ValueError('static_python_invocation_required')
    kwargs = payload['keyword_literals']
    if not isinstance(kwargs, dict) or len(kwargs) > 8:
        raise ValueError('bounded_literal_keywords_required')
    arguments = []
    for key, expression in kwargs.items():
        if not _identifier(key) or not isinstance(expression, str) or len(expression) > 500:
            raise ValueError('literal_keyword_required')
        ast.literal_eval(expression)
        arguments.append(key+'='+expression)
    seed = payload['seed']
    if not isinstance(seed, str) or not 1 <= len(seed) <= 6000:
        raise ValueError('bounded_python_seed_required')
    result = {'status':'not_applicable','contract':payload['contract'],'tests':[],
              'limitations':policy['limitations'],'source_executed':False}
    try:
        inputs = variants(seed, policy['maximum_variants'])
    except (SyntaxError, tokenize.TokenError):
        result['reason'] = 'seed_not_valid_in_current_python_grammar'
        return result
    for index, source in enumerate(inputs):
        call = f'{function}(source'+(' ,'+', '.join(arguments) if arguments else '')+')'
        text = (f'def test_cos_python_syntax_{index}():\n    import ast\n'
                f'    from {module} import {function}\n    source = {source!r}\n'
                f'    result = {call}\n    assert isinstance(result, str)\n'
                '    assert isinstance(ast.parse(result), ast.Module)\n')
        if payload['contract'] == policy['formatting_contract']:
            text += '    assert ast.dump(ast.parse(result)) == ast.dump(ast.parse(source))\n'
        result['tests'].append({'name':f'test_cos_python_syntax_{index}', 'source':text,
            'input':source,'input_ast_preserved':True})
    result.update(status='proposed',variant_count=len(inputs)-1)
    return result
