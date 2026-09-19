"""Bounded same-file syntactic helper context; no execution or import resolution."""
import ast
import re

FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)
MARKER = '\n[... source sections omitted ...]\n'


def _calls(node):
    # Names bound in the caller can shadow a module-level helper. Nested scopes
    # are not traversed as caller execution. These are candidates, never proof.
    bound = {a.arg for a in ast.walk(node.args) if isinstance(a, ast.arg)} if isinstance(node, FUNCTIONS) else set()
    calls = set()
    pending = list(node.body)
    while pending:
        child = pending.pop()
        if isinstance(child, (*FUNCTIONS, ast.ClassDef, ast.Lambda)):
            if hasattr(child, 'name'):
                bound.add(child.name)
            continue
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
            bound.add(child.id)
        if isinstance(child, (ast.Import, ast.ImportFrom)):
            bound.update(a.asname or a.name.split('.')[0] for a in child.names)
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
            calls.add(child.func.id)
        pending.extend(ast.iter_child_nodes(child))
    return calls - bound


def sections(text):
    """Return supplied source spans; accept complete Python or labelled excerpts."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        tree = None
    if tree is not None:
        lines = text.splitlines(keepends=True)
        rows = []
        for node in tree.body:
            if isinstance(node, (*FUNCTIONS, ast.ClassDef)):
                start = min(node.lineno, *(d.lineno for d in node.decorator_list)) if node.decorator_list else node.lineno
                rows.append({'name': node.name, 'text': ''.join(lines[start-1:node.end_lineno]),
                             'calls': _calls(node) if isinstance(node, FUNCTIONS) else set(),
                             'start': start, 'end': node.end_lineno, 'complete': True})
        return rows
    matches = list(re.finditer(r'^\[lines (\d+)-(\d+), ([A-Za-z_]\w*)\]\n', text, re.M))
    rows = []
    for i, match in enumerate(matches):
        body = text[match.end():matches[i+1].start() if i+1 < len(matches) else len(text)].rstrip()
        try:
            parsed = ast.parse(body)
            node = parsed.body[0]
            complete = len(parsed.body) == 1 and isinstance(node, FUNCTIONS) and node.name == match[3]
        except (SyntaxError, IndexError):
            node, complete = None, False
        rows.append({'name': match[3], 'text': text[match.start():match.end()] + body,
                     'calls': _calls(node) if complete else set(), 'start': int(match[1]),
                     'end': int(match[2]), 'complete': complete})
    return rows


def helper_order(rows, roots=None):
    counts = {r['name']: sum(x['name'] == r['name'] for x in rows) for r in rows}
    unique = {r['name']: r for r in rows if counts[r['name']] == 1}
    root_names = roots or [r['name'] for r in rows if not r['name'].startswith('_')]
    visited, queue = set(root_names), list(root_names)
    helpers = []
    while queue:
        name = queue.pop(0)
        for called in sorted(unique.get(name, {}).get('calls', ())):
            if called in unique and called not in visited:
                visited.add(called)
                helpers.append(unique[called])
                queue.append(called)
    return helpers


def select_context(text, budget):
    """Keep complete helper bodies first, plus supplied caller text; always bounded."""
    if len(text) <= budget:
        return text
    rows = sections(text)
    if not rows or budget < len(MARKER) + 80:
        return None
    helpers = helper_order(rows)
    # Labelled abbreviated functions may have unparseable caller bodies. Keep
    # complete short sections as candidates without claiming a call connection.
    candidates = helpers + [r for r in rows if r not in helpers]
    candidates.sort(key=lambda r: (r not in helpers, len(r['text']), r['start']))
    selected, used = [], len(MARKER)
    reserve = min(400, budget // 4)
    for row in candidates:
        cost = len(row['text']) + len(MARKER)
        # An already abbreviated supplied section remains explicitly abbreviated.
        # Preserve it whole rather than hiding its available predicates again.
        if used + cost <= budget - reserve:
            selected.append(row)
            used += cost
    if not selected:
        return None
    # Use a contiguous head to retain imports/caller opening. Missing code is
    # explicit; complete helpers never imply a complete caller/control flow.
    head = text[:max(0, budget - used)]
    return (head + MARKER + MARKER.join(r['text'] for r in sorted(selected, key=lambda r: r['start'])))[:budget]


def lookup_helpers(text, node, *, budget=10000, max_helpers=6):
    """Expand a top-level function within this same hashed file, at most6 helpers."""
    rows = sections(text)
    roots = [r for r in rows if r['name'] == node.name and r['start'] <= node.lineno <= r['end']]
    if len(roots) != 1 or not isinstance(node, FUNCTIONS):
        return None
    root = roots[0]
    chosen = [root]
    omitted = []
    def rendered(row):
        return f"[lines {row['start']}-{row['end']}, {row['name']}]\n" + row['text']
    used = len(rendered(root))
    for row in helper_order(rows, [root['name']]):
        if len(chosen) <= max_helpers and used + 2 + len(rendered(row)) <= budget:
            chosen.append(row)
            used += 2 + len(rendered(row))
        else:
            omitted.append(row['name'])
    excerpt = '\n\n'.join(rendered(r) for r in chosen)
    return {'excerpt': excerpt[:budget], 'helper_context': {
        'authority': 'same_file_syntactic_candidates_not_runtime_binding',
        'ranges': [{'symbol': r['name'], 'line_start': r['start'], 'line_end': r['end']} for r in chosen],
        'omitted_helpers': omitted[:64], 'omitted_helper_count': len(omitted),
        'caller_truncated': len(rendered(root)) > budget}}
