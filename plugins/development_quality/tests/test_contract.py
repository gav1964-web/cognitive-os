from plugins.development_quality.src.main import run


def test_extended_frozen_suite_plan_is_admitted_with_precise_capacity_feedback():
    def proposal(count):
        return {'tests': [{'content': '\n'.join(
            f'def test_case_{i}():\n    assert actual({i}) == {i}\n' for i in range(count))}],
            'case_plan': [{'kind': ('feature', 'preservation', 'boundary')[i % 3],
                           'node': f'test_case_{i}', 'behavior': f'case {i}'} for i in range(count)]}
    assert run({'action': 'validate', 'role': 'spec_writer', 'artifact': proposal(32)})['issues'] == []
    issues = run({'action': 'validate', 'role': 'spec_writer', 'artifact': proposal(129)})['issues']
    assert len(issues) == 1 and '3..128' in issues[0] and 'received 129' in issues[0]


def test_contract_rejects_empty_design_and_tautological_acceptance():
    assert run({'action': 'validate', 'role': 'architect', 'artifact': {}})['issues']
    spec = {'tests': [{'content': 'def test_nothing():\n    assert True\n'}],
            'case_plan': [{'kind': k, 'node': 'test_nothing', 'behavior': 'unchanged'}
                          for k in ('feature', 'preservation', 'boundary')]}
    assert 'constant assertion' in run({'action': 'validate', 'role': 'spec_writer', 'artifact': spec})['issues'][0]


def test_behavioral_assertions_and_real_nodes_are_required():
    spec = {'tests': [{'content': 'def test_value():\n    actual = object()\n    assert actual is not None\n'}],
            'case_plan': [{'kind': k, 'node': 'test_value', 'behavior': k}
                          for k in ('feature', 'preservation', 'boundary')]}
    assert run({'action': 'validate', 'role': 'spec_writer', 'artifact': spec})['issues'] == []
    spec['case_plan'][0]['node'] = 'invented'
    assert run({'action': 'validate', 'role': 'spec_writer', 'artifact': spec})['issues']


def test_selected_existing_preservation_node_requires_actual_source():
    spec = {'tests': [{'content': 'def test_new():\n    assert len([1]) == 1\n'}],
            'regression_tests': ['tests/test_old.py'],
            'case_plan': [{'kind': k, 'node': 'test_new', 'behavior': k}
                          for k in ('feature', 'preservation', 'boundary')]}
    spec['case_plan'][1]['node'] = 'tests/test_old.py::test_old'
    payload = {'action': 'validate', 'role': 'spec_writer', 'artifact': spec}
    assert run(payload)['issues']
    payload['sources'] = [{'path': 'tests/test_old.py', 'content': 'def test_old():\n    assert 1\n'}]
    assert run(payload)['issues'] == []
    spec['regression_tests'] = ['tests/test_other.py']
    assert run(payload)['issues']
