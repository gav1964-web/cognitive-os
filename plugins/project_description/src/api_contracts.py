"""Bounded source facts about API defaults, calls, guards and returned statuses.

This is a syntactic map for review, not an interprocedural proof or code execution.
Only complete, current Python sources explicitly supplied in evidence are read.
"""
import ast
from collections import Counter, deque
import hashlib
import json
from pathlib import Path

from .excerpts import redact_literals
from .source_graph import module_candidates


def _nodes(function):
    pending = list(reversed(function.body))
    while pending:
        node = pending.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        yield node
        pending.extend(reversed(list(ast.iter_child_nodes(node))))


def _read(root, sources, policy):
    if not isinstance(sources, list) or not 1 <= len(sources) <= 6:
        raise ValueError('api_contract_source_count')
    modules = {}
    for row in sources:
        name = row['path']
        path = (root / name).resolve()
        if (Path(name).is_absolute() or '..' in Path(name).parts or not path.is_relative_to(root)
                or path.suffix != '.py' or any(p.startswith('.') or p in policy['excluded_directories'] for p in Path(name).parts)
                or path.name in {'config.py', 'secrets.py', 'credentials.py'}
                or path.stat().st_size > policy['max_file_bytes'] or name in modules):
            raise ValueError('api_contract_source_path')
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != row['sha256']:
            raise ValueError('api_contract_source_changed')
        text = redact_literals(raw.decode('utf-8-sig'))
        tree = ast.parse(text)
        counts = Counter(n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store))
        bindings, functions = {}, {}
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                counts[node.name] += 1
                if isinstance(node, ast.FunctionDef):
                    functions[node.name] = node
                    bindings[node.name] = (name, node.name)
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    base = Path(name).parent.parts
                    base = base[:len(base)-node.level+1]
                    module = '.'.join([*base, *([node.module] if node.module else [])])
                else:
                    module = node.module or ''
                targets = set(module_candidates(module)) & {s['path'] for s in sources}
                for alias in node.names:
                    local = alias.asname or alias.name
                    counts[local] += 1
                    if len(targets) == 1 and alias.name != '*':
                        bindings[local] = (next(iter(targets)), alias.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    counts[alias.asname or alias.name.split('.')[0]] += 1
        bindings = {k: v for k, v in bindings.items() if counts[k] == 1}
        functions = {k: v for k, v in functions.items() if counts[k] == 1}
        if any(isinstance(n, ast.ImportFrom) and any(a.name == '*' for a in n.names) for n in ast.walk(tree)):
            bindings, functions = {}, {}
        modules[name] = {'source_id': row['id'], 'sha256': row['sha256'], 'text': text,
                         'functions': functions, 'bindings': bindings}
    return modules


def _quote(text, node, maximum=160):
    value = ast.get_source_segment(text, node) or ''
    return {'line': node.lineno, 'quote': value[:maximum], 'quote_truncated': len(value) > maximum}


def _facts(module, function):
    args = function.args
    defaults = []
    positional = [*args.posonlyargs, *args.args]
    pairs = [*zip(positional[len(positional)-len(args.defaults):], args.defaults),
             *zip(args.kwonlyargs, args.kw_defaults)]
    for arg, default in pairs:
        if default is not None:
            defaults.append({'parameter': arg.arg, **_quote(module['text'], default)})
    nodes = list(_nodes(function))
    guards = [n for n in nodes if isinstance(n, ast.If)
              and any(isinstance(child, ast.Raise) for body in n.body for child in ast.walk(body))]
    returns = [n for n in nodes if isinstance(n, ast.Return)]
    handlers = [n for n in nodes if isinstance(n, ast.ExceptHandler)]
    values = [n for n in nodes if isinstance(n, ast.Dict)
              and any(isinstance(v, ast.Constant) and isinstance(v.value, (str, bool)) for v in n.values)]
    return {'defaults': defaults, 'guard_excerpts': [_quote(module['text'], n) for n in guards[:3]],
            'return_excerpts': [_quote(module['text'], n) for n in returns[:2]],
            'handler_excerpts': [_quote(module['text'], n) for n in handlers[:1]],
            'result_dictionary_excerpts': [_quote(module['text'], n) for n in values[:2]],
            'facts_limited': len(guards)>3 or len(returns)>2 or len(handlers)>1 or len(values)>2}


def build(root, evidence, requests, policy):
    root = Path(root).resolve(strict=True)
    if Path(evidence['root']).resolve() != root:
        raise ValueError('api_contract_root_mismatch')
    modules = _read(root, evidence['sources'], policy)
    if not isinstance(requests, list) or not 1 <= len(requests) <= 3:
        raise ValueError('api_contract_entry_count')
    queue, seen, functions, edges, limited = deque(), set(), [], [], False
    for request in requests:
        module = modules.get(request['path'])
        if (set(request) != {'path', 'sha256', 'symbol'} or not module
                or module['sha256'] != request['sha256'] or request['symbol'] not in module['functions']):
            raise ValueError('api_contract_entry_changed_or_ambiguous')
        queue.append((request['path'], request['symbol'], 0))
    while queue:
        path, symbol, depth = queue.popleft()
        if (path, symbol) in seen:
            continue
        if len(seen) >= 16:
            limited = True
            break
        seen.add((path, symbol))
        module = modules[path]
        function = module['functions'][symbol]
        if function.decorator_list or len(list(ast.walk(function))) > 1600:
            functions.append({'path': path, 'symbol': symbol, 'status': 'unsupported_definition'})
            continue
        functions.append({'path': path, 'symbol': symbol, 'source_id': module['source_id'],
            'sha256': module['sha256'], 'line': function.lineno, **_facts(module, function)})
        nodes = list(_nodes(function))
        shadowed = {n.id for n in nodes if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
        shadowed.update(a.arg for a in [*function.args.posonlyargs, *function.args.args, *function.args.kwonlyargs])
        shadowed.update(a.arg for a in [function.args.vararg, function.args.kwarg] if a is not None)
        for local in ast.walk(function):
            if isinstance(local, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and local is not function:
                shadowed.add(local.name)
            if isinstance(local, (ast.Import, ast.ImportFrom)):
                shadowed.update(a.asname or a.name.split('.')[0] for a in local.names)
            if isinstance(local, ast.ExceptHandler) and local.name:
                shadowed.add(local.name)
        call_rows = []
        for node in (n for n in nodes if isinstance(n, ast.Call)):
            name = node.func.id if isinstance(node.func, ast.Name) else ''
            target = module['bindings'].get(name) if name not in shadowed else None
            linked = bool(target and target[0] in modules and target[1] in modules[target[0]]['functions'])
            call_rows.append((node, target, linked))
        unresolved = 0
        for node, target, linked in sorted(call_rows, key=lambda r: not r[2]):
            if not linked:
                unresolved += 1
                if unresolved > 3:
                    limited = True
                    continue
            if len(edges) >= 48:
                limited = True
                break
            edge = {'caller': path+':'+symbol, **_quote(module['text'], node, 120),
                    'status': 'syntactic_binding' if linked else 'unresolved',
                    'target': ':'.join(target) if linked else None}
            edges.append(edge)
            if linked:
                if depth < 3:
                    queue.append((*target, depth+1))
                elif target not in seen:
                    limited = True
    result = {'schema_version': 'api_contract_facts.v1', 'functions': functions, 'calls': edges,
              'limited': limited or any(f.get('facts_limited') for f in functions),
              'semantic_verified': False, 'source_executed': False,
              'limits': ['Syntactic bindings only; calls may be conditional or unreachable.',
                         'Unknown imports, attribute dispatch, rebinding and unsupported definitions are not resolved.',
                         'Defaults do not establish successful execution; handlers may convert errors into normal returns.',
                         'Quotations are bounded excerpts; whole-task semantics still require review.']}
    if len(json.dumps(result, ensure_ascii=False)) > 24000:
        return {'schema_version': 'api_contract_facts.v1', 'functions': [], 'calls': [], 'limited': True,
                'semantic_verified': False, 'source_executed': False, 'reason': 'contract_character_budget',
                'omitted_characters': len(json.dumps(result, ensure_ascii=False))}
    return result
