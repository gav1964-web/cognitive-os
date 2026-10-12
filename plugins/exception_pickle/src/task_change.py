"""Goal-level task change: pickle-safe custom exception with its own executable oracle.

Contract `task_competency.v1`: from a user goal and project sources, either refuse with
an explicit reason or return new acceptance tests plus production edits. The caller
owns native red/green qualification, regression comparison and any installation.
Applicability is deliberately explicit and narrow; nothing here executes source.
"""
from __future__ import annotations

import ast
import re
from pathlib import PurePosixPath
from typing import Any

from .candidates import _candidate
from .knowledge import load_exception_pickle_patterns
from .oracle_template import render_test, supported_sample
from .patch import exception_pickle_reconstruction_patch
from .source_samples import _constructor_sample_call, _sample_constructor_value_for_source

CONTRACT = 'task_competency.v1'
GOAL_MARKER = re.compile(r'pickl', re.IGNORECASE)
MAX_REQUIRED = 4


def task_change(goal: str, sources: list[dict[str, str]]) -> dict[str, Any]:
    if not GOAL_MARKER.search(goal):
        return _refuse('goal_does_not_request_pickle_support')
    catalog = load_exception_pickle_patterns()
    operator = dict(catalog.get('operator') or {})
    if catalog.get('status') != 'active' or operator.get('status') != 'validated_active':
        return _refuse('pickle_operator_not_active')
    found = [row for item in sources if _production(item['path']) for row in _candidates(item)]
    named = [row for row in found if re.search(r'\b' + re.escape(row['class_name']) + r'\b', goal)]
    chosen = named or found
    if not chosen:
        return _refuse('no_supported_unpicklable_exception_in_sources')
    if len(chosen) > 1:
        return _refuse('ambiguous_target:' + ','.join(sorted(r['path'] + ':' + r['class_name'] for r in chosen)))
    row = chosen[0]
    required = row['required_constructor_parameters']
    if not 1 <= len(required) <= MAX_REQUIRED or not set(required) <= set(row['stored_constructor_parameters']):
        return _refuse('constructor_inputs_outside_policy')
    recipe = {'operator_id': operator.get('id'), 'reconstruction_method': operator.get('reconstruction_method'),
              'state_strategy': operator.get('state_strategy'), 'required_constructor_inputs': required,
              'allow_keyword_only_state_reducer': bool(row['formatted_super_argument'] or row['keyword_only_required'])}
    patch = exception_pickle_reconstruction_patch(row['source'], class_name=row['class_name'], recipe=recipe)
    if patch is None:
        return _refuse('static_patch_shape_unsupported')
    samples = [_sample_constructor_value_for_source(n, source=row['source'], class_name=row['class_name'])
               for n in required]
    if any(s is None or not supported_sample(s) for s in samples):
        return _refuse('constructor_sample_unsupported')
    args, kwargs = _constructor_sample_call(source=row['source'], class_name=row['class_name'],
                                            required=required, samples=samples)
    located = _module(row['path'])
    if located is None:
        return _refuse('target_module_not_importable_by_path')
    module, import_root = located
    name = _snake(row['class_name'])
    test_path = f"tests/test_cos_pickle_{name}.py"
    test = render_test(module=module, import_root=import_root, class_name=row['class_name'],
                       test_name=f'test_{name}_pickle_round_trip_preserves_state', args=args, kwargs=kwargs)
    return {'status': 'proposed', 'change': {
        'contract': CONTRACT, 'competency': 'exception_pickle',
        'target': f"{row['path']}:{row['class_name']}", 'operator_id': recipe['operator_id'],
        'tests': [{'path': test_path, 'content': test}],
        'edits': [{'path': row['path'], 'content': patch['source']}],
        'acceptance': [f"{row['class_name']} survives pickle round trip with equal type, args and instance state."],
        'limitations': ['Sample constructor values are synthesized from source shape, not from real call sites.',
                        'Only the selected class is changed; subclasses and other exceptions are not audited.']}}


def _refuse(reason: str) -> dict[str, Any]:
    return {'status': 'not_applicable', 'reason': reason}


def _production(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return path.endswith('.py') and not any(p in ('tests', 'test') or p.startswith('test_') for p in parts)


def _candidates(item: dict[str, str]) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(item['content'])
    except SyntaxError:
        return []
    classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
    rows = []
    for node in classes.values():
        row = _candidate(node, local_classes=classes)
        if row:
            init = next(n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == '__init__')
            kwonly = {a.arg for a in init.args.kwonlyargs}
            rows.append({**row, 'path': item['path'], 'source': item['content'],
                         'keyword_only_required': bool(kwonly & set(row['required_constructor_parameters']))})
    return rows


def _module(path: str) -> tuple[str, str] | None:
    """Dotted module and the directory that must be importable (empty: project root)."""
    parts = list(PurePosixPath(path).with_suffix('').parts)
    root: list[str] = []
    if 'src' in parts:
        cut = len(parts) - parts[::-1].index('src')
        root, parts = parts[:cut], parts[cut:]
    if parts and parts[-1] == '__init__':
        parts = parts[:-1]
    if not parts or not all(p.isidentifier() for p in parts):
        return None
    return '.'.join(parts), '/'.join(root)


def _snake(name: str) -> str:
    return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()
