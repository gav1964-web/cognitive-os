"""Resolve optional contrasting acceptance examples; never infer their semantics."""
import ast


def _nodes(path, content):
    try:
        tree = ast.parse(content)
    except (SyntaxError, TypeError):
        return set()
    result = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith('test_'):
            result.add(path + '::' + node.name)
        elif isinstance(node, ast.ClassDef) and node.name.startswith('Test'):
            result.update(path + '::' + node.name + '::' + child.name for child in node.body
                          if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                          and child.name.startswith('test_'))
    return result


def validate_contrasts(artifact, sources):
    pairs = artifact.get('contrast_pairs')
    if pairs is None:
        return []  # Backward-compatible; the semantic auditor still checks adequacy.
    if not isinstance(pairs, list) or not 1 <= len(pairs) <= 24:
        return ['contrast_pairs requires 1..24 executable example pairs when supplied']
    available = set()
    for test in artifact.get('tests', []):
        if isinstance(test.get('path'), str):
            available.update(_nodes(test['path'], test.get('content')))
    selected = artifact.get('regression_tests', [])
    for source in sources:
        path = source.get('path', '')
        if path.startswith('tests/'):
            available.update(node for node in _nodes(path, source.get('content'))
                             if any(node == target or node.startswith(target + '::') for target in selected))
    issues = []
    for pair in pairs:
        if not isinstance(pair, dict) or any(not isinstance(pair.get(k), str) or not pair[k].strip()
                for k in ('left', 'right', 'distinction')):
            issues.append('contrast pair needs left/right test nodes and observable distinction')
            continue
        if pair['left'] == pair['right']:
            issues.append('contrast pair must name different examples, not the same node twice')
        for key in ('left', 'right'):
            reference = pair[key].split('[', 1)[0]
            matches = [node for node in available if node == reference
                       or '::' not in reference and node.rsplit('::', 1)[-1] == reference]
            if len(matches) != 1:
                issues.append('contrast node must resolve uniquely to a supplied new or selected existing test: '
                              + pair[key])
    return list(dict.fromkeys(issues))
