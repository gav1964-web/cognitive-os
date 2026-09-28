"""Domain-neutral source discovery, bounded reads and exact feature edits.

This is a source copy, not an OS security sandbox. Executed tests are trusted
project/model code. Binary corpora and local runtime state are not copied.
"""
import ast
import hashlib
import os
from pathlib import Path

from .stage_finalization_workspace import owned_path, snapshot, _atomic_write

TEXT = {'.py', '.js', '.ts', '.tsx', '.jsx', '.html', '.css', '.json', '.toml',
        '.ini', '.cfg', '.md', '.txt', '.yaml', '.yml'}
EXCLUDE = {'.git', '.venv', 'venv', 'env', '.agents', '.codex', 'node_modules',
           '__pycache__', '.pytest_cache', 'artifacts', 'logs', 'cache', 'outputs',
           'reports', 'generated', 'dist', 'build', '.nft', '.nfi',
           'legacy', 'archive', 'archives', 'backup', 'backups'}


def excluded(part):
    return part.startswith('.') or part.lower() in EXCLUDE or part.lower().endswith(
        ('_outputs', '_reports', '_cache'))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def permitted(name):
    path = Path(name)
    stem = path.stem.lower()
    token_data = ('token' in stem and (path.suffix.lower() != '.py'
                  or stem in {'token', 'tokens'} or stem.endswith(('_token', '_tokens'))))
    return (path.suffix.lower() in TEXT and path.name.lower() != 'config.json'
            and not path.name.startswith('.env')
            and not any(excluded(part) for part in path.parts)
            and not any(word in part.lower() for part in path.parts for word in ('credential', 'secret'))
            and not token_data)


def token_source_admitted(name, source):
    """Narrow code exception, not a claim to detect every embedded secret."""
    if 'token' not in Path(name).stem.lower():
        return True
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    if not any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
               for n in tree.body):
        return False
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        sensitive = any(word in child.id.lower() for target in targets for child in ast.walk(target)
                        if isinstance(child, ast.Name) for word in ('token', 'secret', 'credential'))
        if sensitive and node.value is not None and any(
                isinstance(v, ast.Constant) and isinstance(v.value, (str, bytes)) and v.value
                for v in ast.walk(node.value)):
            return False
    return True


def inventory(project):
    result, total = {}, 0
    for current, dirs, files in os.walk(project):
        dirs[:] = sorted(d for d in dirs if not excluded(d))
        for name in sorted(files):
            relative = (Path(current) / name).relative_to(project).as_posix()
            if not permitted(relative):
                continue
            path = owned_path(project, relative)
            size = path.stat().st_size
            if size > 2_000_000:
                continue
            data = path.read_bytes()
            try:
                source = data.decode('utf-8-sig')
            except UnicodeError:
                continue
            if not token_source_admitted(relative, source):
                continue
            total += len(data)
            result[relative] = digest(data)
            if total > 30_000_000 or len(result) > 2000:
                raise ValueError(f'feature_source_inventory_limit:{len(result)} files/{total} bytes:{relative}')
    return result


def catalog(project, expected):
    rows = []
    for name in expected:
        path = owned_path(project, name)
        row = {'path': name, 'bytes': path.stat().st_size,
               'lines': len(path.read_bytes().splitlines())}
        if path.suffix == '.py':
            try:
                tree = ast.parse(path.read_text(encoding='utf-8-sig'))
                row['symbols'] = [n.name for n in tree.body if isinstance(
                    n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))][:35]
            except SyntaxError:
                row['parse_error'] = True
        rows.append(row)
    return rows


def read_sources(project, expected, requests, *, max_bytes=26000):
    if not isinstance(requests, list) or not 1 <= len(requests) <= 12:
        raise ValueError('feature_read_count')
    result, size = [], 0
    for index, item in enumerate(requests):
        name = item['path']
        if name not in expected:
            raise ValueError('feature_read_not_in_inventory')
        data = owned_path(project, name).read_bytes()
        if digest(data) != expected[name]:
            raise ValueError('feature_source_changed')
        lines = data.decode('utf-8-sig').splitlines(keepends=True)
        start, end = item.get('start', 1), item.get('end', len(lines))
        if not lines and type(start) is int and start == 1 and type(end) is int and end >= 0:
            result.append({'path': name, 'sha256': expected[name], 'start': 1, 'end': 0,
                           'requested_end': end, 'truncated': False, 'eof': True,
                           'total_lines': 0, 'content': ''})
            continue
        if (type(start) is not int or type(end) is not int
                or not 1 <= start <= max(1, len(lines)) or end < start):
            raise ValueError('feature_read_range')
        requested_end = end
        allowance = (max_bytes - size) // (len(requests) - index)
        selected, used = [], 0
        for line in lines[start - 1:end]:
            line = line.replace('\r\n', '\n')
            if used + len(line.encode('utf-8')) > allowance:
                break
            selected.append(line)
            used += len(line.encode('utf-8'))
        if not selected:
            raise ValueError('feature_single_line_exceeds_read_budget')
        end = start + len(selected) - 1
        body = ''.join(selected)
        size += len(body.encode('utf-8'))
        if size > max_bytes:
            raise ValueError('feature_read_byte_limit')
        result.append({'path': name, 'sha256': expected[name], 'start': start,
                       'end': end, 'requested_end': requested_end,
                       'truncated': end < requested_end,
                       'eof': end == len(lines),
                       'total_lines': len(lines), 'content': body})
    return result


def merge_reads(previous, incoming):
    """Keep acquired evidence once, coalescing overlapping line ranges."""
    files = {}
    for row in [*previous, *incoming]:
        info = files.setdefault(row['path'], {'row': row, 'lines': {}})
        if info['row']['sha256'] != row['sha256']:
            raise ValueError('feature_read_cache_source_mismatch')
        for number, line in enumerate(row['content'].splitlines(keepends=True), row['start']):
            info['lines'][number] = line
    result = []
    for name, info in files.items():
        numbers = sorted(info['lines'])
        if not numbers and info['row'].get('total_lines') == 0:
            result.append(dict(info['row']))
            continue
        groups = []
        for number in numbers:
            if not groups or number != groups[-1][-1] + 1:
                groups.append([])
            groups[-1].append(number)
        for group in groups:
            result.append({'path': name, 'sha256': info['row']['sha256'],
                           'start': group[0], 'end': group[-1],
                           'total_lines': info['row']['total_lines'],
                           'content': ''.join(info['lines'][i] for i in group)})
    if sum(len(r['content'].encode('utf-8')) for r in result) > 128000:
        raise ValueError('feature_retained_context_limit')
    return result


def cited_sources(sources, evidence):
    """Select only model-cited, already observed ranges for specification context."""
    result = []
    for row in sources:
        lines = row['content'].splitlines(keepends=True)
        for ref in evidence:
            if ref.get('path') != row['path']:
                continue
            start, end = max(row['start'], ref['start']), min(row['end'], ref['end'])
            if start <= end:
                result.append({**row, 'start': start, 'end': end,
                               'content': ''.join(lines[start - row['start']:end - row['start'] + 1])})
    return merge_reads([], result)


def proposal_for_context(proposal, frozen_tests):
    """After validation, reference literal frozen echoes once rather than repeat code."""
    echoes = [e for e in proposal['edits'] if e['path'] in frozen_tests]
    if not echoes:
        return proposal
    if any(set(e) != {'path', 'source_sha256', 'content'} or e['source_sha256'] is not None
           or not isinstance(e['content'], str)
           or e['content'].encode('utf-8') != frozen_tests[e['path']] for e in echoes):
        raise ValueError('feature_frozen_test_echo_changed')
    return {**proposal, 'edits': [e for e in proposal['edits'] if e['path'] not in frozen_tests],
            'exact_frozen_test_echoes': {e['path']: digest(frozen_tests[e['path']]) for e in echoes}}


def materialize_edits(project, expected, proposals, allowed, *, frozen_tests=None):
    if not isinstance(proposals, list) or not 1 <= len(proposals) <= 8:
        raise ValueError('feature_edit_count')
    edits = {}
    seen = set()
    for item in proposals:
        name = item['path']
        if name in seen:
            raise ValueError('feature_edit_scope')
        seen.add(name)
        if frozen_tests is not None and name in frozen_tests:
            if (set(item) != {'path', 'source_sha256', 'content'}
                    or item['source_sha256'] is not None or not isinstance(item['content'], str)
                    or item['content'].encode('utf-8') != frozen_tests[name]):
                raise ValueError('feature_frozen_test_echo_changed')
            continue  # Exact frozen SpecWriter bytes remain owned by acceptance.
        if name not in allowed or name in edits or not permitted(name) or name.startswith('tests/'):
            raise ValueError('feature_edit_scope')
        path = owned_path(project, name)
        original = path.read_bytes() if name in expected else None
        if item.get('source_sha256') != expected.get(name):
            raise ValueError('feature_edit_stale_hash')
        if original is not None:
            if digest(original) != expected[name]:
                raise ValueError('feature_edit_stale_source')
            text = original.decode('utf-8-sig').replace('\r\n', '\n')
            replacements = item.get('replacements')
            if not isinstance(replacements, list) or not replacements:
                raise ValueError('feature_replacements_required')
            for replacement in replacements:
                old, new = replacement['old'], replacement['new']
                if not old or text.count(old) != 1 or old == new:
                    raise ValueError('feature_replacement_not_unique')
                text = text.replace(old, new, 1)
        else:
            if path.exists():
                raise ValueError('feature_new_file_exists')
            text = item['content']
        if not isinstance(text, str) or len(text.encode('utf-8')) > 120000:
            raise ValueError('feature_edit_size')
        if name.endswith('.py'):
            ast.parse(text)
            old_lines = len(original.splitlines()) if original else 0
            if old_lines <= 400 and len(text.splitlines()) > 400:
                raise ValueError('feature_python_size_growth')
        if original and b'\r\n' in original:
            text = text.replace('\n', '\r\n')
        edits[name] = (b'\xef\xbb\xbf' if original and original.startswith(b'\xef\xbb\xbf') else b'') + text.encode('utf-8')
    if not edits:
        raise ValueError('feature_production_edits_required')
    return edits


def copy_source(project, destination, expected):
    snapshot(project, destination, expected)


def verify_selected_source(project, expected):
    """Check an explicit reviewed source set without reading local runtime state."""
    for name, wanted in expected.items():
        if not permitted(name):
            raise ValueError('feature_selected_source_not_permitted')
        path = owned_path(project, name)
        if not path.is_file() or digest(path.read_bytes()) != wanted:
            raise ValueError('feature_selected_source_changed')


def install(project, expected, edits, backup, *, selected_source=False):
    """COS-owned transaction. Inputs must already be verified by the caller."""
    backup.mkdir(parents=True, exist_ok=False)
    originals, written = {}, []
    lock = project / '.cos-feature.lock'
    with lock.open('x'):
        pass
    try:
        if selected_source:
            verify_selected_source(project, expected)
        elif inventory(project) != expected:
            raise ValueError('feature_source_changed_before_install')
        for name in edits:
            target = owned_path(project, name)
            if name not in expected and target.exists():
                raise ValueError('feature_new_file_exists')
            originals[name] = target.read_bytes() if target.exists() else None
            if originals[name] is not None:
                _atomic_write(owned_path(backup, name), originals[name])
        for name, data in edits.items():
            _atomic_write(owned_path(project, name), data)
            written.append(name)
            if owned_path(project, name).read_bytes() != data:
                raise ValueError('feature_install_readback_failed')
    except BaseException:
        for name in reversed(written):
            target = owned_path(project, name)
            if originals[name] is None:
                target.unlink()
            else:
                _atomic_write(target, originals[name])
        raise
    finally:
        lock.unlink()
    return {'status': 'installed', 'files': {n: digest(b) for n, b in edits.items()},
            'backup': str(backup), 'writer': 'runtime.feature_workspace.install'}
