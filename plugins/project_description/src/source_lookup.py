"""Read explicitly requested, hash-bound code excerpts for one review round."""
import ast
import hashlib
from pathlib import Path

from .excerpts import redact_literals
from .helper_context import lookup_helpers
from .lookup_contract import lookup_kind


def read_requests(root, requests, policy):
    root = Path(root).resolve(strict=True)
    if not isinstance(requests, list) or not 1 <= len(requests) <= 3:
        raise ValueError('description_lookup_count')
    results = []
    for index, request in enumerate(requests):
        relative = request['path']
        path = (root / relative).resolve()
        parts = Path(relative).parts
        kind = lookup_kind(relative)
        if (Path(relative).is_absolute() or '..' in parts or not path.is_relative_to(root)
                or any(p.startswith('.') or p in policy['excluded_directories'] for p in parts)
                or kind is None
                or path.name in {'config.json', 'secrets.json', 'credentials.json'}
                or path.stat().st_size > policy['max_file_bytes']):
            raise ValueError('description_lookup_path')
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != request['sha256']:
            raise ValueError('description_lookup_source_changed')
        text = data.decode('utf-8-sig')
        symbol = request.get('symbol', '')
        expansion = None
        if symbol:
            if path.suffix != '.py':
                raise ValueError('description_lookup_symbol_requires_python')
            try:
                tree = ast.parse(text)
            except SyntaxError as exc:
                raise ValueError('description_lookup_unparseable_source') from exc
            matches = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                       and n.name == symbol]
            if len(matches) != 1:
                raise ValueError('description_lookup_ambiguous_symbol')
            node = matches[0]
            start = min([node.lineno, *[d.lineno for d in node.decorator_list]])
            end = node.end_lineno
            # Redact before the bounded expansion can cut a closing quote off.
            expansion = lookup_helpers(redact_literals(text), node)
        else:
            start, end = request.get('start_line', 1), request.get('end_line', 160)
            if (type(start) is not int or type(end) is not int or start < 1
                    or end < start or end - start > 300):
                raise ValueError('description_lookup_line_range')
        excerpt = redact_literals(expansion['excerpt'] if expansion else '\n'.join(text.splitlines()[start - 1:end]))
        results.append({'id': f'x{index + 1}', 'path': relative, 'sha256': digest,
                        'excerpt': excerpt[:10000], 'truncated': len(excerpt) > 10000,
                        'line_start': start, 'line_end': end, 'surface': {},
                        'primary': False, 'requested': True, 'authority': kind})
        if expansion:
            results[-1]['helper_context'] = expansion['helper_context']
            results[-1]['truncated'] |= expansion['helper_context']['caller_truncated'] or bool(expansion['helper_context']['omitted_helpers'])
    return results
