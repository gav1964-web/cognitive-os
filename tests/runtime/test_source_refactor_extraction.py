import ast
import json
from pathlib import Path

import pytest

from runtime.source_refactor_analysis import analyze_module
from runtime.source_refactor_patch import build_extraction, navigation_edit


FUNCTION = '''def normalize(value: str) -> str:
    """Normalize one caller-provided name."""
    value = value.strip()
    if not value:
        return "unknown"
    return value.lower()
'''


def task_for(tmp_path, source=FUNCTION, name='helpers.py', limit=400):
    (tmp_path / name).write_text(source, encoding='utf-8')
    return analyze_module(tmp_path, name, max_lines=limit)


def plan_for(task, names=None, module='text_normalization'):
    return {'source_sha256': task['sha256'], 'groups': [
        {'module': module, 'reason': 'Normalize textual names with a common empty-value contract.',
         'functions': names or ['normalize']}]}


def test_extracts_exact_body_and_maintains_compatibility_binding(tmp_path):
    task = task_for(tmp_path)
    edits = build_extraction(tmp_path, task, plan_for(task))
    helper = edits['text_normalization.py'].decode()
    original = ast.parse(FUNCTION).body[0]
    moved = next(n for n in ast.parse(helper).body if isinstance(n, ast.FunctionDef))
    assert ast.dump(original) == ast.dump(moved)
    assert edits['helpers.py'].decode().replace('\r\n', '\n') == (
        'from text_normalization import normalize\nnormalize.__module__ = __name__\n')
    assert (tmp_path / 'helpers.py').read_text() == FUNCTION


def test_package_uses_relative_import_and_preserves_future_annotations(tmp_path):
    (tmp_path / 'pkg').mkdir()
    (tmp_path / 'pkg/__init__.py').write_text('')
    task = task_for(tmp_path, 'from __future__ import annotations\n' + FUNCTION, 'pkg/helpers.py')
    edits = build_extraction(tmp_path, task, plan_for(task))
    assert b'from .text_normalization import normalize' in edits['pkg/helpers.py']
    assert b'from __future__ import annotations' in edits['pkg/text_normalization.py']


@pytest.mark.parametrize('source', [
    'state = []\n' + FUNCTION.replace('value = value.strip()', 'state.append(value)'),
    FUNCTION.replace('value = value.strip()', 'global changed\n    changed = value'),
    '@registered\n' + FUNCTION,
    FUNCTION.replace('value = value.strip()', 'value = globals()["value"]'),
    FUNCTION.replace('value = value.strip()', 'value = normalize(value)'),
    FUNCTION.replace('value: str', 'value: DomainValue'),
    FUNCTION.replace('value: str', 'value=[]'),
    'str = custom_type\n' + FUNCTION,
    FUNCTION + FUNCTION,
    FUNCTION.replace('value = value.strip()', 'import os\n    value = os.name'),
    FUNCTION.replace('value = value.strip()', 'def nested():\n        return value'),
    FUNCTION.replace('value = value.strip()', 'value = normalize.__globals__["value"]'),
])
def test_rejects_dependencies_state_and_reflection(tmp_path, source):
    assert not task_for(tmp_path, source)['candidates']


@pytest.mark.parametrize('change', ['stale', 'unknown', 'duplicate', 'escape', 'source', 'collision', 'stdlib', 'package'])
def test_untrusted_plans_cannot_expand_edit_scope(tmp_path, change):
    task = task_for(tmp_path)
    plan = plan_for(task)
    if change == 'stale':
        (tmp_path / 'helpers.py').write_text(FUNCTION + '# changed\n')
    elif change == 'unknown':
        plan['groups'][0]['functions'] = ['missing']
    elif change == 'duplicate':
        plan['groups'][0]['functions'] *= 2
    elif change == 'escape':
        plan['groups'][0]['module'] = '../escape'
    elif change == 'source':
        plan['replacement_source'] = 'pass'
    elif change == 'stdlib':
        plan['groups'][0]['module'] = 'json'
    elif change == 'package':
        (tmp_path / 'text_normalization').mkdir()
    else:
        (tmp_path / 'Text_Normalization.py').write_text('existing = True\n')
    with pytest.raises(ValueError):
        build_extraction(tmp_path, task, plan)


def test_insufficient_split_is_rejected_instead_of_compressing_source(tmp_path):
    task = task_for(tmp_path, FUNCTION + '\n' * 25, limit=20)
    with pytest.raises(ValueError, match='still_exceeds'):
        build_extraction(tmp_path, task, plan_for(task))


def test_navigation_inherits_existing_ownership(tmp_path):
    path = tmp_path / 'docs/architecture/subsystems.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'subsystems': {'roles': {'paths': ['runtime/helpers.py']}}}))
    edits = navigation_edit(tmp_path, {'runtime/helpers.py': ['runtime/text_normalization.py']})
    result = json.loads(edits['docs/architecture/subsystems.json'])
    assert result['subsystems']['roles']['paths'] == ['runtime/helpers.py', 'runtime/text_normalization.py']
