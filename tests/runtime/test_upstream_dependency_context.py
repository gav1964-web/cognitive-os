"""Callee return types and constructor consumers are source context, not authority."""
import pytest

from runtime.upstream_dependency_context import dependency_context
from runtime.repair_diagnostic_context import diagnostic_context


def test_direct_callee_retains_named_tuple_contract_and_hash(tmp_path):
    (tmp_path/'helpers.py').write_text('from typing import NamedTuple\nclass Bounds(NamedTuple):\n    end: int\ndef find(x) -> Bounds:\n    return Bounds(x)\n')
    (tmp_path/'core.py').write_text('from helpers import find\ndef transform(x):\n    return find(x)\n')
    context=dependency_context(tmp_path,'core.py:transform')
    declarations={r['target']:r for r in context['declarations']}
    assert set(declarations)=={'helpers.py:find','helpers.py:Bounds'}
    assert declarations['helpers.py:find']['file_sha256']==declarations['helpers.py:Bounds']['file_sha256']
    assert 'not runtime type proof' in context['limitations']
    issue={'source_dependency_context':context,'failure_evidence_packet':{'target':'core.py:transform'}}
    assert diagnostic_context(issue,tmp_path)['source_dependencies']==context
    (tmp_path/'helpers.py').write_text('# changed')
    with pytest.raises(ValueError,match='source_dependency_context_changed'):
        diagnostic_context(issue,tmp_path)


def test_constructor_context_retains_base_state_and_consumers(tmp_path):
    (tmp_path/'core.py').write_text('''class Base:
    def __init__(self, text):
        self.pending = [text]
class Child(Base):
    def __init__(self, text):
        super().__init__(text)
    def complete(self):
        return ''.join(self.pending)
''')
    rows=dependency_context(tmp_path,'core.py:Child.__init__')['declarations']
    assert {r['target'] for r in rows}=={'core.py:Base','core.py:Child.complete'}


def test_missing_external_helpers_and_budget_are_explicit(tmp_path):
    (tmp_path/'core.py').write_text('from unknown import transform\ndef f(x):\n    return transform(x)\n')
    context=dependency_context(tmp_path,'core.py:f',maximum_chars=1)
    assert context['declarations']==[]
    assert context['unresolved']==['unknown:transform']


def test_callback_argument_and_its_local_helper_are_not_lost(tmp_path):
    (tmp_path/'core.py').write_text('''from functools import partial
def bounds(value):
    return value - 1
def callback(value, flag=False):
    return bounds(value) if flag else value
def unrelated(value):
    return value + 99
def select(flag):
    return partial(callback, flag=flag)
''')
    context=dependency_context(tmp_path,'core.py:select')
    assert {r['target'] for r in context['declarations']}=={'core.py:callback','core.py:bounds'}
    assert all(r['complete_declaration'] for r in context['declarations'])
    bounded=dependency_context(tmp_path,'core.py:select',maximum_chars=1)
    assert bounded['declarations']==[]
    assert set(bounded['omitted'])=={'core.py:callback','core.py:bounds'}
    assert 'does not prove execution' in context['limitations']


def test_imported_callback_reference_and_changed_helper_invalidate_context(tmp_path):
    (tmp_path/'helper.py').write_text('def check(x): return x > 0\ndef callback(x): return check(x)\n')
    (tmp_path/'core.py').write_text('from helper import callback\ndef select(): return callback\n')
    context=dependency_context(tmp_path,'core.py:select')
    assert {r['target'] for r in context['declarations']}=={'helper.py:callback','helper.py:check'}
    issue={'source_dependency_context':context,'failure_evidence_packet':{'target':'core.py:select'}}
    (tmp_path/'helper.py').write_text('def check(x): return x >= 0\ndef callback(x): return check(x)\n')
    with pytest.raises(ValueError,match='source_dependency_context_changed'):
        diagnostic_context(issue,tmp_path)
