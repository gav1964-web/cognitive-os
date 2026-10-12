"""Narrow, explicit preservation-assertion revisions; no execution or approval."""
import ast
import copy


def _shape(node):
    if isinstance(node, ast.Constant):
        return 'value'
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        ast.literal_eval(node)
        return 'value'
    if isinstance(node, (ast.List, ast.Tuple)):
        return type(node).__name__, [_shape(n) for n in node.elts]
    if isinstance(node, ast.Dict):
        return 'dict', [(ast.dump(k), _shape(v)) for k, v in zip(node.keys, node.values)]
    raise ValueError('spec_revision_literal_shape_only')


def revise(spec, proposal, goal, sources):
    """Return a proposal only: equality RHS literals, identical calls/fixtures/keys."""
    if (proposal.get('decision') != 'propose_revision' or not proposal.get('reason')
            or not isinstance(proposal.get('goal_quote'), str)
            or not proposal['goal_quote'].strip() or proposal['goal_quote'] not in goal):
        raise ValueError('spec_revision_goal_evidence_required')
    evidence = proposal.get('source_evidence')
    if not isinstance(evidence, list) or not evidence or any(
            not isinstance(e, dict) or not e.get('quote') or not any(
                s['path'] == e.get('path') and e['quote'] in s['content'] for s in sources)
            for e in evidence):
        raise ValueError('spec_revision_source_evidence_required')
    corrections = proposal.get('corrections')
    if not isinstance(corrections, list) or not 1 <= len(corrections) <= 2:
        raise ValueError('spec_revision_bounded_corrections_required')
    revised = copy.deepcopy(spec)
    seen = set()
    for change in corrections:
        key = change['path'], change['node']
        if key in seen or not change.get('reason'):
            raise ValueError('spec_revision_distinct_nodes_required')
        seen.add(key)
        test = next((t for t in revised['tests'] if t['path'] == change['path']), None)
        if test is None:
            raise ValueError('spec_revision_existing_acceptance_only')
        old, new, body = change['old'], change['new'], test['content']
        tree = ast.parse(body)
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == change['node']]
        nodes = [n for f in functions for n in ast.walk(f) if isinstance(n, ast.Assert)
                 and ast.get_source_segment(body, n) == old]
        replacement = ast.parse(new).body
        if len(nodes) != 1 or body.count(old) != 1 or len(replacement) != 1 or not isinstance(replacement[0], ast.Assert):
            raise ValueError('spec_revision_exact_assertion_required')
        before, after = nodes[0], replacement[0]
        a, b = before.test, after.test
        if (not isinstance(a, ast.Compare) or not isinstance(b, ast.Compare)
                or len(a.ops) != 1 or len(b.ops) != 1
                or not isinstance(a.ops[0], ast.Eq) or not isinstance(b.ops[0], ast.Eq)
                or ast.dump(a.left) != ast.dump(b.left)):
            raise ValueError('spec_revision_equality_rhs_only')
        if (ast.dump(before.msg) if before.msg else None) != (ast.dump(after.msg) if after.msg else None):
            raise ValueError('spec_revision_assert_message_changed')
        ast.literal_eval(a.comparators[0])
        ast.literal_eval(b.comparators[0])
        if _shape(a.comparators[0]) != _shape(b.comparators[0]) or ast.dump(a) == ast.dump(b):
            raise ValueError('spec_revision_literal_structure_changed')
        a.comparators[0] = b.comparators[0]
        updated = body.replace(old, new, 1)
        if ast.dump(tree) != ast.dump(ast.parse(updated)):
            raise ValueError('spec_revision_unrelated_ast_change')
        test['content'] = updated
    return revised
