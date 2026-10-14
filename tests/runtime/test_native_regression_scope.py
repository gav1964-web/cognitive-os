"""A green candidate cannot shrink or skip the baseline regression contract."""
import ast
from pathlib import Path
import sys

import pytest

from runtime.native_regression_scope import verify_regression_scope
from runtime.source_doctest_contract import preserves_doctests
from runtime.upstream_llm_candidates import _replacement
from runtime.stage_finalization_workspace import inventory, snapshot


DOC='def value():\n    """Example.\n\n    >>> value()\n    1\n    """\n    return 1\n'


@pytest.mark.parametrize('change', ['remove','expected','skip','hide'])
def test_model_cannot_weaken_original_doctests(change):
    replacements={
        'remove':'def value():\n    return 1\n',
        'expected':DOC.replace('    1\n','    2\n'),
        'skip':DOC.replace('>>> value()', '>>> value() # doctest: +SKIP'),
        'hide':'def value():\n'+''.join('    '+line+'\n' for line in DOC.splitlines())+'    return 1\n'}
    with pytest.raises(ValueError,match='doctests'):
        _replacement(DOC,'app.py:value',replacements[change])
    assert preserves_doctests(ast.parse(DOC),ast.parse(DOC.replace('Example.', 'Expanded description.')))


def test_static_doctest_guard_also_blocks_non_model_patches(tmp_path):
    baseline=tmp_path/'baseline';baseline.mkdir()
    (baseline/'app.py').write_text(DOC)
    candidate=tmp_path/'candidate';snapshot(baseline,candidate,inventory(baseline))
    (candidate/'app.py').write_text('def value():\n    return 1\n')
    report=verify_regression_scope(root=tmp_path,baseline=baseline,candidate=candidate,intake={})
    assert report['status']=='blocked' and report['reason']=='regression_doctest_contract_changed'
    assert not report['probes']


@pytest.mark.parametrize('mode',['repair','remove_case','skip_case'])
def test_actual_selection_and_skip_comparison(tmp_path,mode):
    baseline=tmp_path/'baseline';(baseline/'tests').mkdir(parents=True)
    source='CASES = [1, 2]\nDISABLED = False\ndef value(x):\n    return 0\n'
    (baseline/'app.py').write_text(source)
    (baseline/'tests/test_app.py').write_text('import pytest\nfrom app import CASES, DISABLED, value\n'
        '@pytest.mark.parametrize("x",CASES)\n@pytest.mark.skipif(DISABLED,reason="disabled")\n'
        'def test_value(x):\n    assert value(x)==x\n')
    candidate=tmp_path/'candidate';snapshot(baseline,candidate,inventory(baseline))
    fixed=source.replace('return 0','return x')
    if mode=='remove_case':fixed=fixed.replace('[1, 2]','[1]')
    if mode=='skip_case':fixed=fixed.replace('DISABLED = False','DISABLED = True')
    (candidate/'app.py').write_text(fixed)
    before=inventory(baseline)
    report=verify_regression_scope(root=tmp_path,baseline=baseline,candidate=candidate,
        intake={'regression_targets':['tests'],'local_editable_install':False,'interpreter_path':sys.executable,
                'pytest_arguments':['-o','addopts='],'timeout_seconds':30})
    assert inventory(baseline)==before
    assert (report['status']=='passed')==(mode=='repair'),report
    if mode=='remove_case':assert report['removed_nodeids']==['tests/test_app.py::test_value[2]']
    if mode=='skip_case':assert len(report['newly_skipped_nodeids'])==2
