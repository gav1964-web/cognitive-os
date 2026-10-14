"""Expose assertions masked by feature failures; never infer their semantics."""
import ast
import hashlib
import json

from .baseline_expectations import classification


def inventory(artifact, frozen_paths=()):
    tests = {t['path']: t['content'] for t in artifact.get('tests', [])}
    rows, limitations = [], []
    for prediction in artifact.get('baseline_expectations', []):
        if classification(prediction) != 'feature_gap':
            continue
        node = prediction['node']
        path, _, symbol = node.partition('::')
        if path in frozen_paths:
            continue  # Accepted bytes retain their original contract.
        body = tests.get(path)
        if body is None:
            continue  # Ordinary admission reports missing test files.
        parts = symbol.split('[')[0].split('::')
        try:
            scope = ast.parse(body).body
            target = None
            for part in parts:
                matches = [n for n in scope if isinstance(n, (ast.ClassDef, ast.FunctionDef,
                                                             ast.AsyncFunctionDef)) and n.name == part]
                if len(matches) != 1:
                    break
                target = matches[0]
                scope = target.body
            else:
                if isinstance(target, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    assertions = sorted((n for n in ast.walk(target) if isinstance(n, ast.Assert)),
                                        key=lambda n: (n.lineno, n.col_offset))
                    if assertions:
                        rows.append({'node': node, 'assertions': [
                            {'id': f'{n.lineno}:{n.col_offset}', 'code': ast.get_source_segment(body, n)}
                            for n in assertions]})
                        continue
        except SyntaxError:
            pass
        limitations.append({'node': node, 'reason': 'No statically located Python assert; ordinary semantic audit still required'})
    binding = {'tests': tests, 'baseline_expectations': artifact.get('baseline_expectations', []),
               'frozen_paths': sorted(frozen_paths)}
    digest = hashlib.sha256(json.dumps(binding, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return {'digest': 'sha256:' + digest, 'feature_gap_assertions': rows,
            'limitations': limitations, 'grants_approval': False}


def validate_review(artifact, audit, frozen_paths=()):
    """Require an auditor partition and separate green controls for invariants.

    Linking is structural; the auditor must check semantic equivalence. Native
    qualification still proves controls execute and pass on the original source.
    """
    if audit.get('decision') != 'approve':
        return []
    catalog = inventory(artifact, frozen_paths)
    if not catalog['feature_gap_assertions']:
        return []
    review = audit.get('baseline_assertion_review')
    if not isinstance(review, dict) or review.get('digest') != catalog['digest']:
        return ['baseline_assertion_review must bind to the supplied assertion inventory digest']
    entries = review.get('tests')
    if not isinstance(entries, list) or any(not isinstance(r, dict) for r in entries):
        return ['baseline_assertion_review.tests must partition every inventoried test']
    nodes = [r.get('node') for r in entries]
    wanted = [r['node'] for r in catalog['feature_gap_assertions']]
    if len(nodes) != len(wanted) or any(nodes.count(n) != 1 for n in wanted):
        return ['baseline_assertion_review must cover every inventoried test exactly once']
    controls = {r['node'] for r in artifact.get('baseline_expectations', [])
                if classification(r) == 'preservation'}
    issues = []
    for source, row in zip(catalog['feature_gap_assertions'],
                           [next(r for r in entries if r['node'] == n) for n in wanted]):
        changed, preserved = row.get('changed'), row.get('preserved')
        if (not isinstance(changed, list) or any(not isinstance(v, str) for v in changed)
                or not isinstance(preserved, list) or any(not isinstance(v, dict) for v in preserved)):
            issues.append(f'{source["node"]}: changed ids and preserved id/control rows are required')
            continue
        covered = [*changed, *(r.get('id') for r in preserved)]
        expected = [a['id'] for a in source['assertions']]
        if len(covered) != len(expected) or any(covered.count(n) != 1 for n in expected):
            issues.append(f'{source["node"]}: every assertion needs exactly one baseline intent; split mixed assertions')
        for item in preserved:
            control = item.get('control')
            if not isinstance(control, str) or control not in controls or control == source['node']:
                issues.append(f'{source["node"]}: preserved assertion {item.get("id")} requires a separate preservation baseline node')
    return issues
