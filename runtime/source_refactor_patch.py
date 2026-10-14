"""Validate declarative moves and construct an exact-source extraction patch."""
from __future__ import annotations

import ast
import fnmatch
import json
import re
import sys
import keyword
from pathlib import Path

from .source_refactor_analysis import analyze_module, digest


def build_extraction(root: Path, task: dict, plan: dict) -> dict[str, bytes]:
    if set(plan) != {'source_sha256', 'groups'} or plan['source_sha256'] != task['sha256']:
        raise ValueError('plan_must_match_frozen_source')
    groups = plan['groups']
    if not isinstance(groups, list) or not 1 <= len(groups) <= 4:
        raise ValueError('one_to_four_cohesive_groups_required')
    fresh = analyze_module(root, task['path'], max_lines=task['max_lines'])
    if fresh['sha256'] != task['sha256']:
        raise ValueError('stale_source')
    candidates = {row['name']: row for row in fresh['candidates']}
    path = Path(task['path'])
    raw = (root / path).read_bytes()
    source = raw.decode('utf-8')
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    newline = '\r\n' if '\r\n' in source else '\n'
    future = [ast.get_source_segment(source, n) for n in tree.body
              if isinstance(n, ast.ImportFrom) and n.module == '__future__']
    edits, replacements, selected, destinations = {}, [], set(), set()
    for group in groups:
        if not isinstance(group, dict) or set(group) != {'module', 'reason', 'functions'}:
            raise ValueError('only_declarative_function_groups_allowed')
        module, names, reason = group['module'], group['functions'], group['reason']
        if (not isinstance(module, str) or not re.fullmatch(r'[a-z][a-z0-9_]{2,59}', module)
                or module.startswith('test_') or module == path.stem or keyword.iskeyword(module)
                or module in sys.stdlib_module_names):
            raise ValueError('invalid_sibling_module_name')
        destination = path.with_name(module + '.py').as_posix()
        if destination.casefold() in destinations or any(
                p.name.casefold() == module.casefold() or p.name.casefold().startswith(module.casefold() + '.')
                for p in (root / path.parent).iterdir()):
            raise ValueError('destination_exists_or_collides')
        if not isinstance(reason, str) or not 12 <= len(reason.strip()) <= 500:
            raise ValueError('cohesion_reason_required')
        if not isinstance(names, list) or not names or any(not isinstance(n, str) for n in names):
            raise ValueError('function_names_required')
        if len(names) != len(set(names)) or set(names) & selected or set(names) - candidates.keys():
            raise ValueError('unknown_duplicate_or_unsupported_function')
        header = '"""Extracted functions; compatibility imports remain in the original module."""'
        chunks = [header, *future, '']
        for name in names:
            row = candidates[name]
            chunks.append(row['source'].rstrip('\r\n'))
            # Bind each name at its original position, retaining __module__ for pickling.
            prefix = '.' if path.parent != Path('.') else ''
            replacement = f'from {prefix}{module} import {name}{newline}{name}.__module__ = __name__{newline}'
            replacements.append((row['start'] - 1, row['end'], replacement))
        content = (newline + newline).join(chunks).rstrip() + newline
        _check_size_and_syntax(content, task['max_lines'])
        edits[destination] = content.encode('utf-8')
        selected.update(names)
        destinations.add(destination.casefold())
    for start, end, replacement in sorted(replacements, reverse=True):
        lines[start:end] = [replacement]
    patched = ''.join(lines)
    _check_size_and_syntax(patched, task['max_lines'])
    if len(patched.splitlines()) >= len(source.splitlines()):
        raise ValueError('extraction_must_reduce_original_size')
    edits[path.as_posix()] = patched.encode('utf-8')
    return edits


def _check_size_and_syntax(source: str, limit: int) -> None:
    ast.parse(source)
    if len(source.splitlines()) > limit:
        raise ValueError('proposed_extraction_still_exceeds_limit')


def navigation_edit(root: Path, moves: dict[str, list[str]]) -> dict[str, bytes]:
    name = 'docs/architecture/subsystems.json'
    path = root / name
    if not path.is_file():
        return {}
    original = path.read_bytes()
    document = json.loads(original)
    for source, destinations in moves.items():
        for spec in document.get('subsystems', {}).values():
            patterns = spec.get('paths', [])
            if not any(fnmatch.fnmatchcase(source, pattern) for pattern in patterns):
                continue
            for destination in destinations:
                if not any(fnmatch.fnmatchcase(destination, pattern) for pattern in patterns):
                    patterns.append(destination)
    updated = (json.dumps(document, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    return {name: updated} if json.loads(original) != document else {}
