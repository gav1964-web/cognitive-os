"""Collect bounded, source-bound facts without executing the inspected project."""
import hashlib
import os
from pathlib import Path

from .excerpts import excerpts
from .surface import source_surface
from .source_graph import source_graph, auxiliary


def _candidate(path):
    name = path.name.lower()
    if name in {'config.json', 'credentials.json', 'secrets.json'} or name.startswith('.'):
        return False
    return (name.startswith('readme') or name in {'pyproject.toml', 'package.json', 'requirements.txt'}
            or path.suffix.lower() in {'.py', '.js', '.ts', '.tsx', '.html', '.bat', '.sh'})


def _priority(relative, size):
    path = Path(relative)
    name = path.name.lower()
    if name.startswith('readme'):
        kind = 0
    elif name in {'app.py', 'main.py', 'index.ts', 'index.js', 'server.py'}:
        kind = 1
    elif name.startswith('test') or any(p in {'tests', 'examples'} for p in path.parts):
        kind = 6
    else:
        kind = {'.py': 2, '.js': 3, '.ts': 3, '.tsx': 3, '.html': 5}.get(path.suffix, 4)
    is_auxiliary = auxiliary(relative)
    metadata = len(path.parts) == 1 and (name.startswith('readme') or name in {
        'pyproject.toml', 'package.json', 'requirements.txt'})
    return (0 if metadata else 2 if is_auxiliary else 1,
            len(path.parts) - 1, kind, -min(size, 100000), relative)



def collect(root, policy):
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError('description_root_not_directory')
    excluded = set(policy['excluded_directories'])
    candidates, omitted = [], []
    count = 0
    traversal_limited = False
    for current, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in excluded and not d.startswith('.')
                         and not (Path(current) / d).is_symlink()
                         and (Path(current) / d).resolve().is_relative_to(root))
        if len(Path(current).relative_to(root).parts) >= policy['max_depth']:
            if dirs:
                traversal_limited = True
            dirs[:] = []
        for name in sorted(names):
            count += 1
            if count > policy['max_discovered_files']:
                traversal_limited = True
                break
            path = Path(current) / name
            if not _candidate(path) or path.is_symlink():
                continue
            if not path.resolve().is_relative_to(root):
                continue
            relative = path.relative_to(root).as_posix()
            try:
                size = path.stat().st_size
            except OSError:
                omitted.append({'path': relative, 'reason': 'unreadable'})
                continue
            if size > policy['max_file_bytes']:
                omitted.append({'path': relative, 'reason': 'file_byte_limit'})
                continue
            candidates.append((relative, size))
        if traversal_limited and count > policy['max_discovered_files']:
            break
    sources, hashes, seen, duplicates = [], {}, {}, []
    remaining = policy['max_total_characters']
    graph = source_graph(root, candidates)
    distance = graph['distance']
    primary = set(sorted((n for n in distance if distance[n] <= 1 and not auxiliary(n)),
                         key=lambda n: (distance[n], _priority(n, 0)))[:12])
    ordered = sorted(candidates, key=lambda x: (0 if x[0] in primary else 1,
                                                distance.get(x[0], 9), _priority(*x)))
    # Reserve supporting-file slots before granting more space to imported code.
    # Otherwise deeper bodies can silently crowd out UI and other independent paths.
    planned = [name for name, _ in ordered[:policy['max_files']]]
    expanded = primary | set(graph['requested_symbols'])
    expanded_count = sum(name in expanded for name in planned)
    secondary_budget = policy.get('secondary_file_characters', 4000)
    reserved = sum(name not in expanded for name in planned) * secondary_budget
    primary_budget = min(policy['max_file_characters'], max(500,
        (policy['max_total_characters'] - reserved) // max(1, expanded_count)))
    for relative, _ in ordered:
        path = root / relative
        try:
            data = path.read_bytes()
            text = data.decode('utf-8-sig')
        except (OSError, UnicodeError):
            omitted.append({'path': relative, 'reason': 'unreadable_or_encoding'})
            continue
        digest = hashlib.sha256(data).hexdigest()
        if digest in seen:
            duplicates.append({'path': relative, 'same_bytes_as': seen[digest]})
            continue
        if len(sources) >= policy['max_files'] or remaining < 500:
            omitted.append({'path': relative, 'reason': 'context_budget'})
            continue
        seen[digest] = relative
        focus = graph['requested_symbols'].get(relative, [])
        per_file = (primary_budget if relative in primary or focus
                    else secondary_budget)
        if path.name.lower().startswith('readme') and primary:
            text = text.split('\n## ', 1)[0][:800]
            per_file = 800
        content, truncated = excerpts(text, path.suffix.lower(), min(remaining, per_file), focus_symbols=focus)
        if path.name.lower().startswith('readme') and primary:
            truncated = len(text.encode('utf-8')) < len(data)
        sources.append({'id': f's{len(sources) + 1}', 'path': relative, 'sha256': digest,
                        'surface': source_surface(text, path.suffix.lower()),
                        'excerpt': content, 'truncated': truncated,
                        'authority': 'documentation_claims' if path.name.lower().startswith('readme') else 'source_excerpt',
                        'primary': relative in primary, 'auxiliary': auxiliary(relative),
                        'local_dependencies': graph['edges'].get(relative, []),
                        'imported_symbols': focus})
        hashes[relative] = digest
        remaining -= len(content)
    if not sources:
        raise ValueError('description_no_readable_sources')
    for relative, digest in hashes.items():
        if hashlib.sha256((root / relative).read_bytes()).hexdigest() != digest:
            raise ValueError('description_source_changed_during_collection')
    return {'schema_version': 'project_description_evidence.v1', 'root': root.as_posix(),
            'sources': sources, 'duplicates': duplicates, 'omitted': omitted,
            'traversal_limited': traversal_limited, 'excluded_directories': sorted(excluded),
            'source_catalog': graph['catalog'], 'catalog_limited': graph['catalog_limited'],
            'dependency_edges': graph['edges'],
            'scope': 'Static excerpts; no execution. Duplicate bytes are not an active-root decision.'}
