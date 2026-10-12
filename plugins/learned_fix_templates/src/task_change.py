"""task_competency.v1 for learned detector-anchored templates (TRY004, G002).

The runtime supplies detector diagnostics; this competency only edits statements
that carry a diagnostic of a rule the goal explicitly asks for, using the most
concrete learned template that matches. Rule-owned safety checks refuse rewrites
the detector alone could not judge (for example G002 placeholder/argument parity).
Verification (detector, regression tests) belongs to the caller.
"""
from __future__ import annotations

import ast
import re
from pathlib import PurePosixPath

from runtime.fix_template_detector import replace_statement
from runtime.fix_template_tree import from_ast, match, substitute, unparse

from .knowledge import load_rules

CONTRACT = 'task_competency.v1'
GOAL_PATTERNS = {
    'TRY004': [r'\bTRY004\b', r'TypeError.{0,80}(isinstance|type[- ]check|проверк\w* тип)',
               r'(isinstance|type[- ]check|проверк\w* тип).{0,80}TypeError'],
    'G002': [r'\bG002\b', r'(logging|logger|лог\w*).{0,80}(%|percent|lazy|ленив\w*|аргумент\w* формат)',
             r'(%|percent|lazy|ленив\w*).{0,80}(logging|logger|лог\w*)'],
}
PLACEHOLDER = re.compile(r'%(?:\(([^)]*)\))?[#0\- +]*(?:\*|\d+)?(?:\.(?:\*|\d+))?[hlL]?([diouxXeEfFgGcrsa%])')


def requested_rules(goal: str, available) -> list:
    return [rule for rule in available
            if any(re.search(p, goal, re.IGNORECASE | re.DOTALL) for p in GOAL_PATTERNS.get(rule, []))]


def _production(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return path.endswith('.py') and not any(p in ('tests', 'test') or p.startswith('test_') for p in parts)


def _site(tree, row):
    best = None
    for node in ast.walk(tree):
        if isinstance(node, ast.stmt) and not hasattr(node, 'body') and \
                node.lineno <= row <= (node.end_lineno or node.lineno):
            if best is None or node.lineno >= best.lineno:
                best = node
    return best


def _g002_safe(before: ast.stmt, after: ast.stmt) -> bool:
    """Placeholders of the format string must equal the positional arguments passed after it."""
    calls = [n for n in ast.walk(after) if isinstance(n, ast.Call) and n.args and isinstance(n.args[0], ast.Constant)
             and isinstance(n.args[0].value, str)]
    if len(calls) != 1:
        return False
    found = PLACEHOLDER.findall(calls[0].args[0].value)
    if any(name for name, kind in found if kind != '%'):
        return False  # mapping-style placeholders need a dict, not positional args
    count = sum(1 for _, kind in found if kind != '%')
    return count == len(calls[0].args) - 1 and not any(isinstance(a, ast.Starred) for a in calls[0].args)


SAFETY = {'G002': _g002_safe}


def _rewrite(rule, templates, node):
    tree = from_ast(node)
    for template in templates:
        binding = match(template['before_tree'], tree)
        if binding is None:
            continue
        rewritten = substitute(template['after_tree'], binding)
        if rewritten.key == tree.key:
            continue
        try:
            code = unparse(rewritten)
            new_node = ast.parse(code).body[0]
        except (AttributeError, TypeError, ValueError, SyntaxError, IndexError):
            continue
        check = SAFETY.get(rule)
        if check and not check(node, new_node):
            return None, 'unsafe_rewrite'
        return code, None
    return None, 'no_matching_template'


def task_change(goal: str, sources, diagnostics) -> dict:
    kb = load_rules()
    rules = requested_rules(goal, kb)
    if not rules:
        return {'status': 'not_applicable', 'reason': 'goal_does_not_request_a_learned_rule'}
    texts = {s['path']: s['content'] for s in sources if _production(s['path'])}
    named = [p for p in texts if p in goal or PurePosixPath(p).name in goal]
    scope = set(named) if named else set(texts)
    edits, sites, skipped = [], [], {}
    for path in sorted(scope):
        rows = sorted({(d['row'], d['code']) for d in diagnostics if d['path'] == path and d['code'] in rules},
                      reverse=True)
        if not rows:
            continue
        source = texts[path]
        try:
            tree = ast.parse(source)
        except SyntaxError:
            skipped['unparsable_source'] = skipped.get('unparsable_source', 0) + 1
            continue
        changed, used = source, set()
        for row, rule in rows:  # bottom-up keeps earlier line numbers valid
            node = _site(tree, row)
            if node is None or node.lineno in used:
                skipped['no_simple_statement'] = skipped.get('no_simple_statement', 0) + 1
                continue
            code, reason = _rewrite(rule, kb[rule]['templates'], node)
            updated = replace_statement(changed, node, code) if code else None
            if not updated:
                key = reason or 'shared_line'
                skipped[key] = skipped.get(key, 0) + 1
                continue
            changed, used = updated, used | {node.lineno}
            sites.append({'path': path, 'row': row, 'rule': rule})
        if changed != source:
            edits.append({'path': path, 'content': changed})
    if not edits:
        return {'status': 'not_applicable', 'reason': 'no_learned_template_applies:' + ','.join(sorted(skipped)) if skipped
                else 'no_diagnostic_of_requested_rule_in_scope'}
    fixed = sorted({s['rule'] for s in sites})
    limitations = ['Templates were learned from history fixes in other projects; correctness is checked by the detector and existing tests only.']
    if skipped:
        limitations.append('Sites left unchanged: ' + ', '.join(f'{k}={v}' for k, v in sorted(skipped.items())))
    if 'TRY004' in fixed:
        limitations.append('TRY004 changes the raised exception type (ValueError -> TypeError); callers catching ValueError may change behavior.')
    return {'status': 'proposed', 'change': {
        'contract': CONTRACT, 'competency': 'learned_fix_templates', 'target': ','.join(e['path'] for e in edits),
        'operator_id': 'learned_templates:' + ','.join(fixed), 'tests': [], 'edits': edits,
        'oracle': {'kind': 'detector', 'tool': 'ruff', 'rules': fixed, 'sites': sites},
        'requires_regression_tests': 'TRY004' in fixed,
        'acceptance': [f'{len(sites)} {"/".join(fixed)} diagnostic(s) removed without new diagnostics; existing referencing tests keep outcomes.'],
        'limitations': limitations}}
