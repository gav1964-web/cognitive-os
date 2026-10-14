"""Declaration overloads must not hide the actual callable or permit duplicate edits."""
import ast
from pathlib import Path

import pytest

from runtime.programmer_python_symbols import qualified_function_matches
from runtime.programmer_structured_edit import apply_structured_replacement
from runtime.project_failure_evidence_packet import _target_source
from runtime.project_development_llm_hypothesis import _target_source as hypothesis_source
from runtime.upstream_candidate_context import candidate_source_context
from runtime.upstream_task_contract import analyze_task_contract

SOURCE = '''import typing as t
@t.overload
def convert(value: int) -> int: ...
@t.overload
def convert(value: str) -> str: ...
def convert(value):
    return value
'''


def test_overloads_bind_implementation_consistently_and_remain_in_patch(tmp_path):
    (tmp_path/'core.py').write_text(SOURCE)
    target='core.py:convert'
    packet=_target_source(tmp_path,target)
    assert packet['line_start']==6
    assert hypothesis_source(tmp_path,target)=='def convert(value):\n    return value'
    patched,reason=apply_structured_replacement(SOURCE,target,'def convert(value):\n    return str(value)')
    assert reason=='structured_function_replacement_applied'
    assert patched.startswith(SOURCE[:SOURCE.index('def convert(value):')])
    assert 'return str(value)' in patched
    context=candidate_source_context(SOURCE+'\n#'+('x'*17000),target)
    assert 'def convert(value):' in context['source']
    contract={'schema_version':'upstream_task_contract.v1','origin':'user_supplied','change_kind':'defect',
              'requirements':[{'id':'R','statement':'Convert value','targets':[target]}]}
    assert analyze_task_contract(tmp_path,contract)['status']=='source_bound'
    from runtime.upstream_change_impact import analyze_change_impact
    assert analyze_change_impact(tmp_path,[target])['interfaces'][target]


@pytest.mark.parametrize('source',[
    SOURCE.replace('@t.overload','@other.overload'),
    SOURCE.replace('import typing as t','import unrelated as t'),
    SOURCE.replace('def convert(value: int) -> int: ...','def convert(value: int) -> int: return 1'),
    SOURCE.replace('def convert(value):','if flag:\n    pass\ndef convert(value):'),
    SOURCE+'\nt = something\n',
    SOURCE.replace('import typing as t','import typing as t\nimport custom as t'),
    SOURCE.replace('def convert(value):','@t.overload\ndef convert(value):'),
    'def convert(x): return x\ndef convert(x): return 1\n',
])
def test_ambiguous_or_executable_duplicate_functions_remain_blocked(source):
    assert len(qualified_function_matches(ast.parse(source),'convert'))>1
    assert apply_structured_replacement(source,'core.py:convert','def convert(value):\n    return 1')[0] is None


def test_direct_alias_overload_and_class_method():
    source=SOURCE.replace('import typing as t','from typing import overload as ov').replace('@t.overload','@ov')
    assert len(qualified_function_matches(ast.parse(source),'convert'))==1
    source='import typing as t\nclass C:\n'+''.join('    '+line+'\n' for line in SOURCE.splitlines()[1:])
    assert len(qualified_function_matches(ast.parse(source),'C.convert'))==1


def test_overloaded_model_delivery_reaches_verified_native_experiment(tmp_path):
    from tests.runtime.test_model_candidate_delivery import _run_case
    from tests.runtime.test_model_requested_delivery import _contract, SOURCE as BODY
    prefix='from typing import overload\n@overload\ndef invert(value: int) -> bool: ...\n@overload\ndef invert(value: bool) -> bool: ...\n'
    project, result=_run_case(tmp_path,source=prefix+BODY,task_contract=_contract())
    assert result['status']=='experiment_validated', result['decision']
    assert (project/'logic.py').read_text().count('@overload')==2
