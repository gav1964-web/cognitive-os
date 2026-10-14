"""Mine detector-anchored statement edits from full-history repositories (offline, no LLM).

For every non-merge commit touching 1-3 production Python files, both file versions are
read with one `git cat-file --batch` process, ruff runs once over all versions, and
statement edits that resolve a ruff diagnostic are written as JSONL records. Old file
versions stay on disk for the ruff-autofix baseline. Lazy fetching is disabled.
"""
import argparse
import ast
import json
import os
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.fix_template_detector import anchor, run_ruff  # noqa: E402
from runtime.fix_template_mining import MAX_EDIT_NODES, MAX_SOURCE_BYTES, production_python, statement_pairs  # noqa: E402
from runtime.fix_template_tree import from_ast, size  # noqa: E402

ENV = {**os.environ, 'GIT_NO_LAZY_FETCH': '1', 'GIT_TERMINAL_PROMPT': '0'}


def _commits(repo, limit):
    log = subprocess.run(['git', '-C', str(repo), 'log', '--no-merges', '--no-renames', f'-n{limit}',
                          '--format=@@%H|%ct', '--name-only'], capture_output=True, encoding='utf-8',
                         errors='replace', env=ENV, timeout=1800).stdout
    rows = []
    for block in log.split('@@')[1:]:
        head, _, names = block.partition('\n')
        sha, _, ts = head.partition('|')
        files = [n.strip() for n in names.splitlines() if production_python(n.strip())]
        if 1 <= len(files) <= 3:
            rows.extend((sha, int(ts or 0), f) for f in files)
    return rows


def _blobs(repo, names):
    proc = subprocess.Popen(['git', '-C', str(repo), 'cat-file', '--batch'], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, env=ENV)
    data, _ = proc.communicate(''.join(n + '\n' for n in names).encode('utf-8'), timeout=3600)
    out, pos = [], 0
    for _ in names:
        end = data.index(b'\n', pos)
        header = data[pos:end].split()
        pos = end + 1
        if len(header) == 3 and header[1] == b'blob':
            length = int(header[2])
            blob = data[pos:pos + length]
            pos += length + 1
            out.append(blob.decode('utf-8', 'replace') if length <= MAX_SOURCE_BYTES else None)
        else:
            out.append(None)
    return out


def mine(name, repo, work, limit):
    rows = _commits(repo, limit)
    texts = _blobs(repo, [n for sha, _, path in rows for n in (f'{sha}^:{path}', f'{sha}:{path}')])
    folder = work / 'versions' / name
    folder.mkdir(parents=True, exist_ok=True)
    pairs = []
    for i, (sha, ts, path) in enumerate(rows):
        old, new = texts[2 * i], texts[2 * i + 1]
        if old and new and old != new:
            (folder / f'{i}_o.py').write_text(old, encoding='utf-8')
            (folder / f'{i}_n.py').write_text(new, encoding='utf-8')
            pairs.append((i, sha, ts, path, old, new))
    diags = run_ruff(folder)
    records = []
    for i, sha, ts, path, old, new in pairs:
        before, after = diags.get(f'{i}_o.py', []), diags.get(f'{i}_n.py', [])
        if not (Counter(d['code'] for d in before) - Counter(d['code'] for d in after)):
            continue
        for b, a, rule, fixable in anchor(statement_pairs(old, new), before, after):
            tb, ta = from_ast(b), from_ast(a)
            if size(tb) > MAX_EDIT_NODES or size(ta) > MAX_EDIT_NODES or tb.key == ta.key:
                continue
            records.append({'project': name, 'commit': sha, 'time': ts, 'path': path, 'rule': rule,
                            'ruff_fixable': fixable, 'old_file': f'versions/{name}/{i}_o.py', 'line': b.lineno,
                            'before': ast.unparse(b), 'after': ast.unparse(a)})
    return name, len(rows), len(pairs), records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', action='append', required=True, help='name=path')
    parser.add_argument('--work', required=True)
    parser.add_argument('--limit', type=int, default=6000)
    args = parser.parse_args()
    work = Path(args.work).resolve()
    work.mkdir(parents=True, exist_ok=True)
    repos = dict(r.split('=', 1) for r in args.repo)
    total = []
    with ThreadPoolExecutor(4) as pool:
        for name, commits, changed, records in pool.map(lambda kv: mine(kv[0], Path(kv[1]), work, args.limit), repos.items()):
            total.extend(records)
            print(name, 'file-commits', commits, 'changed', changed, 'anchored', len(records), flush=True)
    with open(work / 'anchored.jsonl', 'w', encoding='utf-8') as handle:
        for record in total:
            handle.write(json.dumps(record, ensure_ascii=False) + '\n')
    print('anchored edits', len(total), 'rules', len({r['rule'] for r in total}))


if __name__ == '__main__':
    main()
