"""Fixtures are evidence, not execution authority or invented complete context."""
import ast
import json

from runtime.failure_test_context import test_support_context
from runtime.project_failure_evidence_packet import _test_source
from runtime.project_failure_prompt_context import test_source_groups as group_sources


SOURCE = '''import pytest
import json
VALUE = "x"
def helper():
    return VALUE
@pytest.fixture
def workspace(tmp_path):
    return helper()
def unrelated():
    raise RuntimeError("never execute")
def test_owned(workspace):
    assert workspace == "x"
'''


def context(source=SOURCE, limit=10000):
    tree = ast.parse(source)
    return test_support_context(source, tree, tree.body[-1], limit=limit)


def test_collects_transitive_fixture_helper_constant_and_decorator_import():
    result = context()
    text = '\n'.join(r['excerpt'] for r in result['sources'])
    assert '@pytest.fixture' in text and 'def workspace' in text and 'def helper' in text
    assert 'VALUE = "x"' in text and 'import pytest' in text
    assert 'import json' not in text and 'unrelated' not in text
    assert result['authority'] == 'diagnostic_only' and not result['pytest_fixture_resolution_complete']


def test_budget_omits_whole_sources_without_claiming_completeness():
    result = context(limit=15)
    assert result['truncated'] and result['omitted_lines'] and result['content_bytes'] <= 15
    for row in result['sources']:
        ast.parse(row['excerpt'])


def test_ambiguous_rebindings_are_not_silently_selected():
    result = context('def helper(): return 1\ndef helper(): return 2\ndef test_case(): assert helper()==1\n')
    assert result['ambiguous_names'] == ['helper'] and result['sources'] == []


def test_recursion_is_bounded_without_executing_support():
    result = context('def helper(): return helper()\ndef test_case(): assert helper()\n')
    assert len(result['sources']) == 1


def test_packet_and_prompt_group_retain_source_bound_fixture(tmp_path):
    (tmp_path/'test_case.py').write_text(SOURCE,encoding='utf-8')
    row = _test_source(tmp_path,'test_case.py::test_owned')
    grouped = group_sources([row])[0]
    assert grouped['support_context'] == row['support_context']
    assert row['file_sha256'] and '@pytest.fixture' in json.dumps(grouped)
