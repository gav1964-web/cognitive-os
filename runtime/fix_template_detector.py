"""Detector anchoring for learned fix templates, using ruff as an independent detector.

An edit is anchored to rule R when a ruff diagnostic R lies inside the replaced
statement before the commit and no R diagnostic lies inside the replacement after it.
The detector also localizes where a template may be applied and serves as an
automatic oracle: a suggestion is detector-verified when the rewritten file parses,
the anchored diagnostic disappears at that statement and no new diagnostic appears.
"""
from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

IGNORED = 'D,ANN,CPY,ERA,COM,Q,I,E501,W291,W293,W391,EM,FIX,TD,INP,T20,FBT,ARG,N,S101,PLR2004,BLE,RUF100,E402'


def ruff_executable() -> str:
    local = Path(sys.executable).with_name('ruff.exe' if os.name == 'nt' else 'ruff')
    found = str(local) if local.exists() else shutil.which('ruff')
    if not found:
        raise RuntimeError('ruff_not_installed')
    return found


def run_ruff(directory: Path, *, select: str = 'ALL', ignore: str = IGNORED, fix: bool = False) -> dict:
    """Diagnostics per file name (relative to directory): [{'code','row','end_row','fixable'}]."""
    args = [ruff_executable(), 'check', '--isolated', '--no-cache', '--exit-zero', '--select', select,
            '--output-format', 'json', '--target-version', 'py38']
    if ignore:
        args += ['--ignore', ignore]
    if fix:
        args += ['--fix', '--unsafe-fixes']
    run = subprocess.run([*args, str(directory)], capture_output=True, encoding='utf-8', errors='replace', timeout=3600)
    rows = json.loads(run.stdout or '[]')
    out: dict = {}
    for row in rows:
        name = Path(row['filename']).resolve().relative_to(directory.resolve()).as_posix()
        out.setdefault(name, []).append({'code': row['code'], 'row': row['location']['row'],
                                         'end_row': row['end_location']['row'], 'fixable': row.get('fix') is not None})
    return out


def _inside(diag, node) -> bool:
    return node.lineno <= diag['row'] <= (node.end_lineno or node.lineno)


def anchor(pairs, before_diags, after_diags):
    """Yield (before_node, after_node, rule, ruff_fixable) for diagnostics resolved by a statement edit."""
    for before, after in pairs:
        old = Counter(d['code'] for d in before_diags if _inside(d, before))
        new = Counter(d['code'] for d in after_diags if _inside(d, after))
        for code, count in (old - new).items():
            fixable = any(d['fixable'] for d in before_diags if d['code'] == code and _inside(d, before))
            yield before, after, code, fixable


def statements_with_rule(source: str, diags, rule: str):
    """Statements (innermost simple statements) carrying a diagnostic of `rule`."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError):
        return []
    rows = {d['row'] for d in diags if d['code'] == rule}
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.stmt) and not hasattr(node, 'body') and any(
                node.lineno <= r <= (node.end_lineno or node.lineno) for r in rows):
            found.append(node)
    return found


def replace_statement(source: str, node, new_code: str) -> str:
    """Replace the source lines of a simple statement, keeping its indentation."""
    lines = source.splitlines(keepends=True)
    start, end = node.lineno - 1, (node.end_lineno or node.lineno)
    first = lines[start]
    if first[:node.col_offset].strip():  # statement shares a line with others (e.g. `a; b`)
        return None
    indent = first[:node.col_offset]
    newline = '\r\n' if first.endswith('\r\n') else '\n'
    body = ''.join(indent + line + newline for line in new_code.splitlines())
    return ''.join(lines[:start]) + body + ''.join(lines[end:])


def detector_verified(original: str, rewritten: str, node, rule: str, workdir: Path) -> bool:
    """Rewritten file parses, `rule` no longer fires in the edited lines, and no new diagnostics appear."""
    try:
        ast.parse(rewritten)
    except (SyntaxError, ValueError):
        return False
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / 'old.py').write_text(original, encoding='utf-8')
    (workdir / 'new.py').write_text(rewritten, encoding='utf-8')
    diags = run_ruff(workdir)
    old, new = diags.get('old.py', []), diags.get('new.py', [])
    span = range(node.lineno, node.lineno + len(rewritten.splitlines()) - len(original.splitlines())
                 + (node.end_lineno or node.lineno) - node.lineno + 1)
    still = any(d['code'] == rule and d['row'] in span for d in new)
    return not still and not (Counter(d['code'] for d in new) - Counter(d['code'] for d in old))
