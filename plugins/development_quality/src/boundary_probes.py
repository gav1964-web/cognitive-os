"""Bounded syntactic boundary foils; validity still needs goal-backed native evidence."""
import ast


REPLACEMENTS = {
    ast.Gt: (ast.NotEq, ast.GtE), ast.GtE: (ast.Gt, ast.NotEq),
    ast.Lt: (ast.NotEq, ast.LtE), ast.LtE: (ast.Lt, ast.NotEq),
    ast.Eq: (ast.LtE, ast.GtE), ast.NotEq: (ast.Gt, ast.Lt),
}


def boundary_probes(sources, limit=8):
    """Suggest exact comparison replacements without executing source or asserting defects."""
    if not isinstance(limit, int) or not 1 <= limit <= 8:
        raise ValueError('boundary_probe_limit')
    probes = []
    for source in sources:
        if not source.get('path', '').endswith('.py'):
            continue
        content = source.get('content', '')
        try:
            tree = ast.parse(content)
        except (SyntaxError, TypeError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare) or len(node.ops) != 1:
                continue
            if not any(isinstance(n, ast.Constant) and type(n.value) in (int, float)
                       for n in ast.walk(node)):
                continue
            old = ast.get_source_segment(content, node)
            if not old or content.count(old) != 1:
                continue
            for operator in REPLACEMENTS.get(type(node.ops[0]), ()):
                new = ast.unparse(ast.Compare(left=node.left, ops=[operator()], comparators=node.comparators))
                probes.append({'path': source['path'], 'source_sha256': source['sha256'],
                    'line': source.get('start', 1) + node.lineno - 1,
                    'old': old, 'new': new,
                    'status': 'unvalidated_hypothesis',
                    'question': 'Which valid input, combined with other parameters, distinguishes these conditions '
                                'in the public result? A differing predicate alone does not prove a goal violation.'})
                if len(probes) >= limit:
                    return probes
    return probes
