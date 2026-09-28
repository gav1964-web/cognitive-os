"""Bounded same-module test support excerpts; never execute fixture code."""
import ast
import hashlib


def test_support_context(text: str, tree: ast.Module, test: ast.AST, *, limit=10000) -> dict:
    """Collect named fixture/helper dependencies, not a complete pytest resolver.

    Imports are evidence only. External fixtures, conftest, dynamic lookups and
    runtime rebinding remain unresolved; excerpts grant no target authority.
    """
    definitions = {}
    for node in tree.body:
        names = []
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names = [node.name]
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names = [n.id for target in targets for n in ast.walk(target) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)]
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.asname or (a.name.split('.')[0] if isinstance(node, ast.Import) else a.name)
                     for a in node.names if a.name != '*']
        for name in names:
            definitions.setdefault(name, []).append(node)

    def references(node):
        names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.update(a.arg for a in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs])
        return names

    pending = sorted(references(test))
    seen, selected, ambiguous = set(), {}, []
    while pending and len(seen) < 256:
        name = pending.pop(0)
        if name in seen:
            continue
        seen.add(name)
        choices = definitions.get(name, [])
        if len(choices) > 1:
            ambiguous.append(name)
            continue
        if not choices or choices[0] is test:
            continue
        node = choices[0]
        if node.lineno in selected:
            continue
        selected[node.lineno] = node
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            pending.extend(sorted(references(node) - seen))
    rows, used, omitted = [], 0, []
    lines = text.splitlines()
    for _, node in sorted(selected.items()):
        start = min([node.lineno, *[d.lineno for d in getattr(node, 'decorator_list', [])]])
        excerpt = '\n'.join(lines[start-1:node.end_lineno])
        size = len(excerpt.encode('utf-8'))
        if len(rows) >= 32 or used + size > limit:
            omitted.append(start)
            continue
        used += size
        rows.append({'line': start, 'line_end': node.end_lineno, 'excerpt': excerpt,
                     'sha256': hashlib.sha256(excerpt.encode('utf-8')).hexdigest()})
    return {'scope': 'same_module_named_dependencies_only', 'authority': 'diagnostic_only',
            'pytest_fixture_resolution_complete': False, 'sources': rows,
            'ambiguous_names': sorted(ambiguous), 'omitted_lines': omitted,
            'truncated': bool(omitted or pending), 'content_bytes': used}


test_support_context.__test__ = False
