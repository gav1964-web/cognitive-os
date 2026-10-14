from pathlib import Path
import sys

from plugins.development_quality.evaluation.native import evaluate_candidate, evaluate_spec


def test_evaluation_detects_cross_module_fault_and_copies_new_helper(tmp_path):
    fixed = {'consumer.py': 'from helper import twice\ndef public(x):\n    return twice(x)\n',
             'helper.py': 'def twice(x):\n    return x * 2\n'}
    wrong = {**fixed, 'helper.py': 'def twice(x):\n    return x\n'}
    task = {'original':wrong,'reference':fixed,'mutants':[wrong],
            'existing':'from consumer import public\ndef test_zero():\n    assert public(0)==0\n',
            'oracle':'from consumer import public\ndef test_value():\n    assert public(3)==6\n'}
    spec = {'tests':[{'path':'tests/test_change.py','content':task['oracle']}],
            'regression_tests':['tests/test_existing.py'],'environment':{}}
    result = evaluate_spec(task,spec,tmp_path/'spec',Path(sys.executable))
    assert result['status']=='valid' and result['killed']==1
    candidate = tmp_path/'candidate';candidate.mkdir()
    (candidate/'consumer.py').write_text('from extra import twice\ndef public(x):\n    return twice(x)\n')
    (candidate/'extra.py').write_text(fixed['helper.py'])
    assert evaluate_candidate(task,candidate,tmp_path/'candidate-check',Path(sys.executable))['passed']
