"""Plugin-owned development contracts. Pure admission, no inference or execution."""
import ast
import json
from pathlib import Path
from .boundary_probes import boundary_probes
from .draft_cases import compare_draft


def policy():
    return json.loads((Path(__file__).resolve().parents[1] / 'knowledge/policy.json').read_text(encoding='utf-8'))


def validate(role, artifact, sources=()):
    issues = []
    if role in ('analyzer', 'architect'):
        scope = artifact.get('scope')
        if not isinstance(scope, list) or not 1 <= len(scope) <= 4 or any(
                not isinstance(n, str) or not n.endswith('.py') or n.startswith('tests/') for n in scope):
            issues.append('scope must contain 1..4 production Python files; existing tests are evidence, not edit targets')
    if role == 'architect':
        for key, fields in [('states', ('id', 'when', 'evidence', 'expected', 'unknown_behavior')),
                            ('counterexamples', ('input', 'wrong', 'expected', 'because'))]:
            rows = artifact.get(key)
            if not isinstance(rows, list) or not 2 <= len(rows) <= 12:
                issues.append(f'{key}: require 2..12 concrete cases')
            elif any(not isinstance(row, dict) or any(f not in row or
                    isinstance(row[f], str) and not row[f].strip() for f in fields) for row in rows):
                issues.append(f'{key}: each case needs {fields}')
    elif role == 'spec_writer':
        names = set()
        existing = set()
        for source in sources:
            if not source.get('path', '').startswith('tests/'):
                continue
            try:
                tree = ast.parse(source['content'])
                existing.update(source['path'] + '::' + n.name for n in ast.walk(tree)
                                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))
            except (SyntaxError, KeyError, TypeError):
                continue
        for test in artifact.get('tests', []):
            try:
                tree = ast.parse(test['content'])
            except (SyntaxError, KeyError, TypeError):
                issues.append('test source must parse before native qualification')
                continue
            names.update(n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))
            for node in ast.walk(tree):
                if isinstance(node, ast.Assert):
                    expr = node.test
                    if isinstance(expr, ast.Constant) or (isinstance(expr, ast.Compare)
                            and all(isinstance(x, ast.Constant) for x in [expr.left, *expr.comparators])):
                        issues.append('constant assertion is not behavioral evidence')
                    if any(isinstance(x, ast.IfExp) and isinstance(x.test, ast.Constant) for x in ast.walk(expr)):
                        issues.append('constant conditional assertion is not behavioral evidence')
        plan = artifact.get('case_plan', [])
        if not isinstance(plan, list):
            issues.append('case_plan must be a list of executable coverage rows')
        elif not 3 <= len(plan) <= 128:
            issues.append(f'case_plan requires 3..128 rows; received {len(plan)}. Group equivalent cases without removing executable coverage.')
        else:
            kinds = {r.get('kind') for r in plan if isinstance(r, dict)}
            if not {'feature', 'preservation', 'boundary'} <= kinds:
                issues.append('case_plan lacks feature/preservation/boundary')
            regression = artifact.get('regression_tests', [])
            for row in plan:
                if not isinstance(row, dict) or not isinstance(row.get('node'), str):
                    issues.append('case_plan rows require node strings')
                    continue
                node = row['node'].split('[')[0]
                selected_existing = node in existing and any(
                    node == target or node.startswith(target + '::') for target in regression)
                if (node.split('::')[-1] not in names and not selected_existing) or not row.get('behavior'):
                    issues.append(f'case_plan node {node} must name a new test or selected existing test supplied in source')
    elif role != 'analyzer':
        raise ValueError('quality_unsupported_role')
    return list(dict.fromkeys(issues))


def run(payload):
    data = policy()
    if payload['action'] == 'policy':
        return {'contract': data['contract'], 'policy': data}
    if payload['action'] == 'validate':
        return {'contract': data['contract'], 'issues': validate(payload['role'], payload['artifact'], payload.get('sources', []))}
    if payload['action'] == 'boundary_probes':
        return {'contract': data['contract'], 'probes': boundary_probes(payload.get('sources', []))}
    if payload['action'] == 'compare_draft':
        return {'contract': data['contract'], **compare_draft(payload['previous'], payload['current'])}
    raise ValueError('quality_unsupported_action')
