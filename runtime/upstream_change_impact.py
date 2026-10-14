"""Bounded syntactic call references, with explicit incompleteness."""
import ast
import hashlib
from pathlib import Path

from .narrow_type_evidence_binding import content_digest
from .stage_finalization_workspace import inventory, owned_path
from .upstream_call_bindings import call_bindings
from .python_overload_resolution import implementation_candidates


def symbol_interface(project: Path, target: str) -> str:
    name, _, symbol = target.partition(':')
    tree = ast.parse(owned_path(project, name).read_bytes().decode('utf-8-sig'))
    scope = tree.body
    node = None
    for part in symbol.split('.'):
        found = [n for n in scope if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == part]
        found = implementation_candidates(tree, found)
        if len(found) != 1:
            raise ValueError('unique_symbol_required')
        node, scope = found[0], found[0].body
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        raise ValueError('function_target_required')
    return content_digest({'kind': type(node).__name__, 'args': ast.dump(node.args),
        'returns': ast.dump(node.returns) if node.returns else None,
        'decorators': [ast.dump(n) for n in node.decorator_list]})


def analyze_change_impact(project: Path, targets: list[str]) -> dict:
    leaves = {t.rsplit('.', 1)[-1].rsplit(':', 1)[-1] for t in targets}
    paths = sorted(p for p in inventory(project) if p.endswith('.py'))
    references, scanned, omitted = [], {}, []
    total_bytes = 0
    for index, name in enumerate(paths):
        path = owned_path(project, name)
        size = path.stat().st_size
        if index >= 128 or size > 1_000_000 or total_bytes + size > 4_000_000:
            omitted.append(name)
            continue
        data = path.read_bytes()
        total_bytes += len(data)
        try:
            tree = ast.parse(data.decode('utf-8-sig'))
        except (UnicodeError, SyntaxError):
            omitted.append(name)
            continue
        scanned[name] = hashlib.sha256(data).hexdigest()
        for binding in call_bindings(tree, name, set(targets)):
            node = binding['node']
            leaf = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else None
            if leaf not in leaves and not binding['resolved_targets']:
                continue
            if len(references) >= 128:
                omitted.append(name)
                break
            references.append({'path': name, 'line': node.lineno, 'callee': ast.unparse(node.func),
                'source_sha256': scanned[name], 'classification': 'possible_name_reference',
                'target_resolution': 'static_binding' if binding['resolved_targets'] else 'not_proven',
                'resolved_targets': binding['resolved_targets']})
    result = {'schema_version': 'upstream_change_impact.v1', 'targets': targets,
        'interfaces': {t: symbol_interface(project, t) for t in targets},
        'possible_callers': references, 'scanned_sources': scanned, 'omitted_sources': sorted(set(omitted)),
        'complete_call_graph': False, 'external_callers': 'not_observed',
        'limitations': 'bounded module/import bindings; dynamic dispatch, runtime rebinding, import hooks and external consumers unresolved; no complete call graph'}
    result['impact_digest'] = content_digest(result)
    return result
