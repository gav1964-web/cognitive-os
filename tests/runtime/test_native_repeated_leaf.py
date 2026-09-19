"""Multiple failing tests must not move a repeated leaf behind its caller."""
from pathlib import Path
import sys

from runtime.native_failure_acceptance import _probe
from runtime.project_native_failure_binding import _interpret_pytest_result


def test_direct_and_wrapped_failures_keep_repeated_exception_leaf(tmp_path):
    project=tmp_path/'project';project.mkdir()
    (project/'app.py').write_text('def leaf():\n    return [][0]\ndef wrapper():\n    return leaf()\n')
    (project/'test_app.py').write_text('from app import leaf, wrapper\n'
        'def test_direct():\n    leaf()\ndef test_wrapped():\n    wrapper()\n')
    probe=_probe(project,tmp_path/'probe',['test_app.py'],[],30,Path(sys.executable))
    assert probe['returncode']==1
    output=Path(probe['output']).read_text(encoding='utf-8')
    bound=_interpret_pytest_result(project,1,output,{})
    assert len(bound['failing_nodeids'])==2
    assert bound['production_targets']==['app.py:wrapper','app.py:leaf']
    assert bound['leaf_production_target']=='app.py:leaf'
