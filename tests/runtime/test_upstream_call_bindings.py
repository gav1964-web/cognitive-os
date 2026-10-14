"""Static caller evidence must preserve uncertainty and source identity."""
import pytest

from runtime.upstream_change_impact import analyze_change_impact


def make_project(tmp_path, caller, *, caller_path='caller.py'):
    (tmp_path / 'core.py').write_text('def read(value):\n    return value\n', encoding='utf-8')
    path = tmp_path / caller_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(caller, encoding='utf-8')
    return analyze_change_impact(tmp_path, ['core.py:read'])


@pytest.mark.parametrize('caller', [
    'from core import read as fetch\ndef use(x):\n    return fetch(x)\n',
    'import core as c\ndef use(x):\n    return c.read(x)\n',
    'import core\ncore.read(1)\n',
    'from core import read\ndef unrelated():\n    global state\n    state = 1\nread(1)\n',
])
def test_import_aliases_link_to_exact_source_target(tmp_path, caller):
    r = make_project(tmp_path, caller)
    assert len(r['possible_callers']) == 1
    row = r['possible_callers'][0]
    assert row['resolved_targets'] == ['core.py:read']
    assert row['target_resolution'] == 'static_binding'
    assert row['source_sha256'] == r['scanned_sources']['caller.py']
    assert r['complete_call_graph'] is False


@pytest.mark.parametrize('caller', [
    'from core import read\ndef use(read):\n    return read(1)\n',
    'from core import read\ndef use():\n    read = other\n    return read(1)\n',
    'from core import read\nread = other\nread(1)\n',
    'if condition:\n    from core import read\nread(1)\n',
    'from core import read\ndef use():\n    global read\n    read = other\nread(1)\n',
    'from core import read\nfrom other import *\nread(1)\n',
    'from core import read\nexec(code)\nread(1)\n',
    'from core import read\nitems = [read(1) for read in funcs]\n',
    'from other import read\nread(1)\n',
    'def read(x):\n    return x\nread(1)\n',
    'from core import read\ndef outer(read):\n    def inner():\n        return read(1)\n',
])
def test_shadowing_and_unrelated_names_do_not_claim_target(tmp_path, caller):
    r = make_project(tmp_path, caller)
    assert r['possible_callers']
    assert all(row['resolved_targets'] == [] for row in r['possible_callers'])
    assert all(row['target_resolution'] == 'not_proven' for row in r['possible_callers'])


def test_relative_import_in_package(tmp_path):
    package = tmp_path / 'pkg'
    package.mkdir()
    (package / '__init__.py').write_text('')
    (package / 'core.py').write_text('def read(x):\n    return x\n')
    (package / 'caller.py').write_text('from .core import read as fetch\nfetch(1)\n')
    r = analyze_change_impact(tmp_path, ['pkg/core.py:read'])
    assert r['possible_callers'][0]['resolved_targets'] == ['pkg/core.py:read']


def test_source_change_invalidates_impact_digest(tmp_path):
    r = make_project(tmp_path, 'from core import read\nread(1)\n')
    (tmp_path / 'caller.py').write_text('from other import read\nread(1)\n')
    changed = analyze_change_impact(tmp_path, ['core.py:read'])
    assert r['impact_digest'] != changed['impact_digest']
    assert changed['possible_callers'][0]['resolved_targets'] == []


def test_method_dispatch_remains_unproven(tmp_path):
    (tmp_path / 'core.py').write_text('class Reader:\n    def read(self, x):\n        return x\n')
    (tmp_path / 'caller.py').write_text('from core import Reader\nReader.read(obj, 1)\n')
    r = analyze_change_impact(tmp_path, ['core.py:Reader.read'])
    assert r['possible_callers'][0]['target_resolution'] == 'not_proven'
