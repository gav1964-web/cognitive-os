"""Mine single-statement fix edits (before -> after) from a repository's git history.

Read-only and offline: uses `git log`/`git show` on an existing clone with lazy
fetching disabled, so partial clones yield only locally present blobs; never writes. An edit is a 1:1 statement replacement inside aligned statement lists of a
fix-labelled commit touching few production Python files. Test files are excluded.
"""
from __future__ import annotations

import ast
import difflib
import os
import re
import subprocess
from pathlib import Path, PurePosixPath

from .fix_template_tree import from_ast, size

FIX_MESSAGE = re.compile(r'\b(fix(e[sd])?|bug|crash|error|incorrect|regression|handle|wrong)\b', re.IGNORECASE)
MAX_FILES = 3
MAX_EDIT_NODES = 80
MAX_SOURCE_BYTES = 300_000
COMPOUND = {'If', 'For', 'AsyncFor', 'While', 'With', 'AsyncWith', 'Try', 'FunctionDef', 'AsyncFunctionDef', 'ClassDef'}


def _git(repo, *args, timeout=900):
    # Offline only: partial clones must not lazily download missing blobs from a remote.
    env = {**os.environ, 'GIT_NO_LAZY_FETCH': '1', 'GIT_TERMINAL_PROMPT': '0'}
    return subprocess.run(['git', '-C', str(repo), *args], capture_output=True, timeout=timeout,
                          encoding='utf-8', errors='replace', env=env).stdout


def production_python(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return path.endswith('.py') and not any(
        p in ('tests', 'test', 'testing', 'docs', 'examples') or p.startswith(('test_', 'conftest')) for p in parts)


def fix_commits(repo, limit=3000):
    """Yield (sha, timestamp, subject, files) for fix-labelled non-merge commits, oldest first."""
    log = _git(repo, 'log', '--no-merges', '--no-renames', f'-n{limit}', '--format=@@%H|%ct|%s', '--name-only')
    rows = []
    for block in log.split('@@')[1:]:
        head, _, names = block.partition('\n')
        sha, ts, subject = (head.split('|', 2) + ['', ''])[:3]
        files = [n.strip() for n in names.splitlines() if n.strip()]
        py = [f for f in files if production_python(f)]
        if FIX_MESSAGE.search(subject) and 1 <= len(py) <= MAX_FILES:
            rows.append((sha, int(ts or 0), subject, py))
    return list(reversed(rows))


def _source(repo, rev, path):
    text = _git(repo, 'show', f'{rev}:{path}')
    return text if text and len(text) <= MAX_SOURCE_BYTES else None


def _parse(text):
    try:
        return ast.parse(text)
    except (SyntaxError, ValueError, RecursionError):
        return None


def _stmt_key(node):
    return ast.dump(node, annotate_fields=False)


def _same_header(a, b):
    if type(a) is not type(b):
        return False
    if isinstance(a, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return a.name == b.name
    return type(a).__name__ in COMPOUND


def _align(before, after, out):
    keys_b, keys_a = [_stmt_key(s) for s in before], [_stmt_key(s) for s in after]
    matcher = difflib.SequenceMatcher(a=keys_b, b=keys_a, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != 'replace' or i2 - i1 != j2 - j1:
            continue
        for b, a in zip(before[i1:i2], after[j1:j2]):
            if _same_header(b, a) and _headers_equal(b, a):
                for name in ('body', 'orelse', 'finalbody'):
                    _align(getattr(b, name, []) or [], getattr(a, name, []) or [], out)
                for hb, ha in zip(getattr(b, 'handlers', []), getattr(a, 'handlers', [])):
                    _align(hb.body, ha.body, out)
            else:
                out.append((b, a))


def _headers_equal(b, a):
    strip = lambda n: _stmt_key(type(n)(**{f: (getattr(n, f) if f not in ('body', 'orelse', 'finalbody', 'handlers') else [])
                                          for f in n._fields}))
    try:
        return strip(b) == strip(a)
    except TypeError:
        return False


def statement_pairs(before_text, after_text):
    """Aligned 1:1 replaced statements as AST nodes (with original line numbers)."""
    before, after = _parse(before_text), _parse(after_text)
    if before is None or after is None:
        return []
    pairs = []
    _align(before.body, after.body, pairs)
    return pairs


def edits_from_sources(before_text, after_text):
    result = []
    for b, a in statement_pairs(before_text, after_text):
        tb, ta = from_ast(b), from_ast(a)
        if size(tb) <= MAX_EDIT_NODES and size(ta) <= MAX_EDIT_NODES and tb.key != ta.key:
            result.append((tb, ta))
    return result


def mine_repository(repo, project, limit=3000):
    """Return edit records with provenance for one repository."""
    records, seen = [], set()
    for sha, ts, subject, files in fix_commits(repo, limit):
        for path in files:
            old, new = _source(repo, sha + '^', path), _source(repo, sha, path)
            if not old or not new:
                continue
            for b, a in edits_from_sources(old, new):
                identity = (b.key, a.key)
                if identity in seen:
                    continue
                seen.add(identity)
                records.append({'project': project, 'commit': sha, 'time': ts, 'subject': subject[:120],
                                'path': path, 'before': b, 'after': a})
    return records


def head_statements(repo, maximum_files=400):
    """Statement trees of the current production sources (for false-positive measurement)."""
    from .fix_template_tree import iter_statements
    out = []
    files = [f for f in _git(repo, 'ls-files', '*.py').splitlines() if production_python(f)][:maximum_files]
    for name in files:
        path = Path(repo) / name
        try:
            tree = _parse(path.read_text(encoding='utf-8'))
        except (OSError, UnicodeDecodeError):
            continue
        if tree is not None:
            out.extend(s for s in iter_statements(from_ast(tree)) if size(s) <= MAX_EDIT_NODES)
    return out
