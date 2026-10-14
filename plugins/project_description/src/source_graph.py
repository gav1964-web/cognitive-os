"""Bounded static import edges and source inventory, without module execution."""
import ast
import hashlib
import posixpath
import re
from pathlib import Path

AUXILIARY = {'tools', 'tests', 'examples', 'legacy', 'packaging', 'scratch'}
ENTRYPOINTS = {'app.py', 'main.py', 'server.py', 'api_server.py', '__main__.py',
               'cli.py', 'index.js', 'index.ts', 'index.html'}


def auxiliary(name):
    path = Path(name)
    return bool(AUXILIARY.intersection(path.parts[:-1]) or path.name == 'conftest.py'
                or path.name.startswith('test_'))


def module_candidates(module):
    stem = module.replace('.', '/')
    return [prefix + stem + suffix for prefix in ('', 'src/')
            for suffix in ('.py', '/__init__.py')]


def inspect_source(name, text, names):
    edges, symbols, entry, imports = set(), [], False, {}
    if name.endswith('.py'):
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return edges, symbols, entry, imports
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                symbols.append(node.name)
            if isinstance(node, ast.Call):
                called = getattr(node.func, 'id', '')
                if called in {'FastAPI', 'Flask', 'ArgumentParser'}:
                    entry = True
            if isinstance(node, ast.Import):
                for alias in node.names:
                    edges.update(set(module_candidates(alias.name)) & names)
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    base = Path(name).parent.parts
                    base = base[:len(base) - node.level + 1]
                    module = '.'.join([*base, *([node.module] if node.module else [])])
                    candidates = module_candidates(module)
                    for alias in node.names:
                        candidates += module_candidates(module + '.' + alias.name)
                else:
                    module = node.module or ''
                    candidates = module_candidates(module)
                    for alias in node.names:
                        candidates += module_candidates(module + '.' + alias.name)
                edges.update(set(candidates) & names)
                for target in set(module_candidates(module)) & names:
                    imports.setdefault(target, set()).update(a.name for a in node.names if a.name != '*')
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value in names:
                    edges.add(node.value)
        # Package public API also matters when there is no executable entrypoint.
        entry = entry or (Path(name).name == '__init__.py' and bool(edges))
    if Path(name).suffix in {'.html', '.js', '.ts', '.tsx'}:
        for ref in re.findall(r'''(?:src=|from\s*|import\s*)["']([^"']+)["']''', text):
            ref = ref.split('?', 1)[0]
            candidate = ref.lstrip('/') if ref.startswith('/') else posixpath.normpath(
                posixpath.join(posixpath.dirname(name), ref))
            for choice in (candidate, candidate + '.js', candidate + '.ts'):
                if choice in names:
                    edges.add(choice)
    return edges - {name}, list(dict.fromkeys(symbols))[:24], entry, imports


def source_graph(root, candidates):
    names = {name for name, _ in candidates}
    catalog, edges, entries, imports = [], {}, set(), {}
    # Inspect application files before auxiliary files under the same fixed bound.
    ordered = sorted(candidates, key=lambda r: (auxiliary(r[0]), len(Path(r[0]).parts), r[0]))[:160]
    for name, _ in ordered:
        try:
            data = (root / name).read_bytes()
            text = data.decode('utf-8-sig')
        except (OSError, UnicodeError):
            continue
        linked, symbols, detected, imports[name] = inspect_source(name, text, names)
        edges[name] = sorted(linked)
        if not auxiliary(name) and (Path(name).name in ENTRYPOINTS or detected):
            entries.add(name)
        catalog.append({'path': name, 'sha256': hashlib.sha256(data).hexdigest(),
                        'symbols': symbols, 'auxiliary': auxiliary(name)})
    distance = {name: 0 for name in entries}
    for level in range(2):
        for name in sorted(n for n, d in distance.items() if d == level):
            for target in edges.get(name, []):
                if target not in distance:
                    distance[target] = level + 1
    requested = {}
    for name, targets in imports.items():
        if distance.get(name, 9) > 1 or auxiliary(name):
            continue
        for target, symbols in targets.items():
            requested.setdefault(target, set()).update(symbols)
    return {'catalog': catalog, 'catalog_limited': len(candidates) > 160,
            'edges': edges, 'distance': distance,
            'requested_symbols': {name: sorted(symbols) for name, symbols in requested.items()}}
