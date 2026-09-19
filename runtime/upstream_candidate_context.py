"""Bound model context independently from the full file used for exact edits."""
import ast
import hashlib
from .python_overload_resolution import implementation_candidates


def candidate_source_context(source: str, target: str) -> dict:
    if len(source.encode('utf-8')) > 1_000_000:
        raise ValueError('candidate_source_budget_exceeded')
    digest = hashlib.sha256(source.encode('utf-8')).hexdigest()
    if len(source) <= 16000:
        return {'source': source, 'file_sha256': digest, 'complete_module': True,
            'scope': 'complete_module', 'omitted_statement_count': 0}
    tree = ast.parse(source)
    scope = tree.body
    for part in target.partition(':')[2].split('.'):
        matches = [n for n in scope if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and n.name == part]
        matches = implementation_candidates(tree, matches)
        if len(matches) != 1:
            raise ValueError('candidate_context_target_not_unique')
        function = matches[0]
        scope = function.body
    if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
        raise ValueError('candidate_context_function_required')
    selected = [function]
    needed = _loads(function)
    declarations = [(n, _declares(n)) for n in tree.body if n is not function]
    # Include static dependencies transitively, preserving their original order.
    for _ in range(64):
        added = [n for n, names in declarations if n not in selected and names & needed]
        if not added:
            break
        selected.extend(added)
        for node in added:
            needed.update(_loads(node))
        if len(selected) > 64:
            raise ValueError('candidate_context_dependency_budget_exceeded')
    excerpt = '\n\n'.join(ast.get_source_segment(source, n) or '' for n in sorted(selected, key=lambda n: n.lineno))
    if len(excerpt) > 16000:
        raise ValueError('candidate_context_budget_exceeded')
    return {'source': excerpt, 'file_sha256': digest, 'complete_module': False,
        'scope': 'target_and_static_dependencies',
        'omitted_statement_count': sum(n not in selected for n in tree.body),
        'limitations': 'Static name dependencies only; runtime mutation, dynamic lookup and callers may be absent. This excerpt is not a replacement file.'}


def _loads(node):
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}


def _declares(node):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return {node.name}
    if isinstance(node, ast.Import):
        return {a.asname or a.name.split('.')[0] for a in node.names}
    if isinstance(node, ast.ImportFrom):
        return {a.asname or a.name for a in node.names}
    if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
        return {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
    return set()
