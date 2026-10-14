"""Real role/executor/native runs with explicitly scripted model responses."""
import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from runtime.local_inference import LocalInferenceConfig
from runtime.native_failure_acceptance import _probe
from runtime.narrow_type_evidence_binding import content_digest
from runtime.project_development import run_project_development, load_project_development_policy
from runtime.stage_finalization_workspace import inventory, snapshot
from runtime.upstream_model_delivery import validate_delivery_intent

TARGET = 'logic.py:invert'
NODE = 'tests/test_logic.py::test_false'
SOURCE = 'def invert(value: bool) -> bool:\n    return bool(value)\n'
TESTS = '''from logic import invert

def test_false():
    assert invert(False) is True

def test_true():
    assert invert(True) is False
'''


def _run_case(work, *, replacement='return not bool(value)', source=SOURCE,
              task_contract=None, expected_calls=2, proposal_route='hypothesis', authorize_model_trial=False,
              native_plugin=False):
    project = work / 'input'
    (project / 'tests').mkdir(parents=True)
    (project / 'logic.py').write_text(source, encoding='utf-8')
    (project / 'tests/test_logic.py').write_text(TESTS, encoding='utf-8')
    (project / 'pyproject.toml').write_text("[project]\nname='model-delivery-fixture'\nversion='0.1.0'\n", encoding='utf-8')
    plugins = ['env_plugin'] if native_plugin else []
    if native_plugin:
        (project/'env_plugin.py').write_text('def pytest_addoption(parser):\n    parser.addoption("--native-environment-flag", action="store_true")\n')
        (project/'pytest.ini').write_text('[pytest]\naddopts = --native-environment-flag\n')
    repetitions = []
    for i in range(2):
        probe = _probe(project, work / f'intake-{i}', [NODE], plugins, 15, Path(sys.executable))
        assert probe['returncode'] == 1
        repetitions.append({'failure_signature': probe['intake_signature'], 'exit_code': 1,
            'leaf_production_target': TARGET, 'production_targets': [TARGET],
            'output_tail': Path(probe['output']).read_text(encoding='utf-8')})
    failure = {'target': TARGET, 'failure_signature': repetitions[0]['failure_signature'],
        'authority': 'failing_contract_test', 'failing_nodeids': [NODE], 'detail': repetitions[0]['output_tail']}
    hypothesis = {'target': TARGET, 'failure_signature': failure['failure_signature'],
        'mechanism': 'The implementation returns the original truth value instead of its inverse.',
        'repair_mechanism': 'Negate the boolean conversion while preserving the callable interface.',
        'mutation_contract': {'precondition': 'The source returns the unchanged truth value.',
            'change': 'Return the complement of the supplied boolean value.',
            'preserved_behavior': 'Keep the same argument and boolean return annotation.'},
        'residual_risks': ['Both false and true inputs require native verification.'], 'confidence': 0.8}
    response = {'candidates': [{'id': 'invert-truth', 'reason': 'Test negating the observed truth value.',
        'replacement_source': 'def invert(value: bool) -> bool:\n    ' + replacement + '\n'}]}
    calls = []
    def check_request(messages):
        if task_contract is not None:
            from runtime.upstream_task_contract import normalize_task_contract
            assert json.loads(messages[1]['content'])['task_contract'] == normalize_task_contract(task_contract)
    def advisory(messages, config=None):
        check_request(messages)
        calls.append(('hypothesis', config))
        return hypothesis
    def candidate(messages, config=None):
        check_request(messages)
        calls.append(('candidate', config))
        return response
    policy = deepcopy(load_project_development_policy())
    if native_plugin:
        policy['native_failure_intake']['nested_pytest_plugins'] = plugins
        policy['native_failure_intake']['pytest_arguments'].extend(['-p', 'env_plugin'])
    policy['model_proposal_route'] = proposal_route
    policy['native_failure_intake'].update(local_editable_install=False, interpreter_path=sys.executable,
        regression_targets=[], nested_pytest_plugins=plugins, timeout_seconds=20)
    from runtime.upstream_llm_trials import validate_llm_diagnosis_proposals
    from runtime.programmer_executor import run_programmer_executor
    from runtime.upstream_requested_change import bind_requested_change
    before = inventory(project)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr('runtime.project_development_llm_hypothesis.call_json_chat', advisory)
        patch.setattr('runtime.upstream_llm_trials.call_json_chat', candidate)
        patch.setattr('runtime.project_development_core.enrich_failure_diagnosis',
            lambda *a, **kw: pytest.fail('delivery consulted training KB'))
        patch.setattr('runtime.programmer_patch_strategy.call_json_chat',
            lambda *a, **kw: pytest.fail('delivery regenerated model code'))
        patch.setattr('runtime.upstream_llm_trials.validate_llm_diagnosis_proposals',
            lambda *a, **kw: validate_llm_diagnosis_proposals(*a, **{**kw, 'root': work}))
        patch.setattr('runtime.project_development_experiment.run_programmer_executor',
            lambda **kw: run_programmer_executor(**{**kw, 'execution_base_dir': work / 'exec'}))
        patch.setattr('runtime.upstream_requested_change.bind_requested_change',
            lambda *a, **kw: bind_requested_change(*a, **{**kw, 'root': work}))
        result = run_project_development(root=Path(__file__).resolve().parents[2], project_dir=project,
            goal='Invert the boolean input', run_sandbox_experiment=True, policy=policy,
            chain_case={'project_stratum': 'library_pure_transform', 'contract_failure_evidence': [failure],
                        'repetitions': repetitions},
            authorize_training_replay=not authorize_model_trial, authorize_model_trial=authorize_model_trial,
            validate_causal_proposals=True,
            llm_hypothesis_config=LocalInferenceConfig(base_url='http://example.test/v1', model='scripted'),
            task_contract=task_contract)
    (work / 'run.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    assert inventory(project) == before
    assert len(calls) == expected_calls
    if expected_calls == 2:
        assert calls[0][1] is calls[1][1]
    return project, result


@pytest.fixture(scope='module')
def delivered(tmp_path_factory):
    project, result = _run_case(tmp_path_factory.mktemp('model-delivery'))
    assert result['status'] == 'experiment_validated', {
        'status': result['status'], 'handoff': result['role_chain_handoff'],
        'experiment': result['experiment']}
    return project, result


def test_selected_model_bytes_reach_full_native_regression_and_final_reviewer(delivered):
    project, result = delivered
    issue = result['decision']['selected_issue']
    ticket = issue['model_delivery']
    assert ticket['authority'] == 'explicit_model_candidate_replay'
    assert issue['allowed_operator_ids'] == []
    experiment = result['experiment']
    assert (Path(experiment['sandbox_project']) / 'logic.py').read_bytes() == ticket['replacement_source'].encode('utf-8')
    assert content_digest(inventory(Path(experiment['sandbox_project']))) == ticket['patched_inventory_digest']
    assert experiment['final_review']['conformance_status'] == 'passed'
    assert experiment['final_review']['recommendation'] == 'approve'
    native = json.loads(Path(experiment['test_result_path']).read_text(encoding='utf-8'))
    assert native['project_native_verification']['regression_suite']['status'] == 'passed'
    assert native['post_regression_source_check']['status'] == 'passed'
    assert (project / 'logic.py').read_text(encoding='utf-8') == SOURCE


@pytest.mark.parametrize('field,value', [('candidate_id', 'another'), ('patched_inventory_digest', 'fake'),
    ('source_inventory_digest', 'fake'), ('replacement_source', SOURCE), ('source_apply', True)])
def test_resealed_delivery_tampering_is_rejected(delivered, field, value):
    _, result = delivered
    intent = deepcopy(result['role_artifacts']['technical_spec']['implementation_delta']['intent'])
    ticket = intent['model_delivery']
    ticket[field] = value
    ticket['delivery_digest'] = content_digest({k: v for k, v in ticket.items() if k != 'delivery_digest'})
    with pytest.raises(ValueError, match='model_delivery'):
        validate_delivery_intent(intent)


def test_stale_source_is_blocked_before_materialization(delivered, tmp_path):
    from runtime.programmer_model_delivery import model_delivery_package
    project, result = delivered
    clone = tmp_path / 'stale'
    snapshot(project, clone, inventory(project))
    (clone / 'logic.py').write_text(SOURCE + '# unrelated edit\n', encoding='utf-8')
    artifacts = result['role_artifacts']
    response = model_delivery_package(execution_dir=tmp_path / 'run', project_dir=clone,
        implementation_plan=artifacts['implementation_plan'], test_plan=artifacts['test_plan'])
    assert response['status'] == 'blocked' and response['reason'] == 'model_delivery_source_changed'
    assert not (tmp_path / 'run').exists()


def test_targeted_model_success_cannot_override_full_native_failure(tmp_path):
    _, result = _run_case(tmp_path, replacement='return not bool(value) if value is False else bool(value)')
    assert result['decision']['selected_issue']['causal_comparison']['status'] == 'selected_for_regression'
    assert result['status'] != 'experiment_validated'
    experiment = result['experiment']
    assert experiment['status'] == 'failed'
    native = json.loads(Path(experiment['test_result_path']).read_text(encoding='utf-8'))
    assert native['project_native_verification']['regression_suite']['status'] == 'test_failed'
    assert experiment['final_review']['recommendation'] != 'approve'
    assert result['validated_memory']['status'] == 'not_promoted'


@pytest.mark.parametrize('removed', ['model_delivery', 'causal_comparison', 'authority'])
def test_delivery_cannot_fall_back_to_generation_if_plan_is_weakened(delivered, tmp_path, monkeypatch, removed):
    from runtime.programmer_executor import run_programmer_executor
    project, result = delivered
    artifacts = deepcopy(result['role_artifacts'])
    artifacts['implementation_plan']['implementation_delta']['intent'].pop(removed)
    monkeypatch.setattr('runtime.programmer_executor.synthesize_patch_package',
        lambda **kw: pytest.fail('invalid delivery reached synthesis'))
    monkeypatch.setattr('runtime.programmer_patch_strategy.call_json_chat',
        lambda *a, **kw: pytest.fail('invalid delivery invoked model'))
    response = run_programmer_executor(root=tmp_path, project_dir=project,
        technical_spec=artifacts['technical_spec'], implementation_plan=artifacts['implementation_plan'],
        test_plan=artifacts['test_plan'], use_l45_llm=True)
    assert response['status'] == 'blocked'


def test_final_review_rejects_another_green_patch_and_missing_comparison(delivered):
    from runtime.upstream_causal_review import causal_comparison_checks
    _, result = delivered
    spec = deepcopy(result['role_artifacts']['technical_spec'])
    acceptance = json.loads(Path(result['experiment']['test_result_path']).read_text(encoding='utf-8'))['executable_acceptance_result']
    assert all(r['passed'] for r in causal_comparison_checks(spec, acceptance))
    assert not all(r['passed'] for r in causal_comparison_checks(spec,
        {**acceptance, 'patched_inventory_digest': 'another-green-patch'}))
    spec['implementation_delta']['intent'].pop('causal_comparison')
    assert not all(r['passed'] for r in causal_comparison_checks(spec, acceptance))


def test_testplan_substitution_is_blocked_before_copy(delivered, tmp_path):
    from runtime.programmer_model_delivery import model_delivery_package
    project, result = delivered
    artifacts = deepcopy(result['role_artifacts'])
    artifacts['test_plan']['executable_acceptance']['packet']['failing_nodeids'] = ['tests/test_logic.py::test_true']
    response = model_delivery_package(execution_dir=tmp_path / 'run', project_dir=project,
        implementation_plan=artifacts['implementation_plan'], test_plan=artifacts['test_plan'])
    assert response['status'] == 'blocked'
    assert not (tmp_path / 'run').exists()


@pytest.mark.parametrize('corruption', ['training_origin', 'missing_provenance', 'operator'])
def test_model_delivery_cannot_be_relabelled_as_training(delivered, corruption):
    from runtime.upstream_causal_review import causal_comparison_checks
    _, result = delivered
    spec = deepcopy(result['role_artifacts']['technical_spec'])
    intent = spec['implementation_delta']['intent']
    comparison = intent['causal_comparison']
    selected = comparison['attempts'][0]
    if corruption == 'training_origin':
        comparison['candidate_origin'] = selected['origin'] = 'training_rule_proposal'
    elif corruption == 'missing_provenance':
        selected.pop('provenance')
    else:
        selected['operator_id'] = intent['operator_id'] = 'guard_mapping_path_descent'
    comparison['comparison_digest'] = content_digest({k: v for k, v in comparison.items() if k != 'comparison_digest'})
    ticket = intent['model_delivery']
    ticket['comparison_digest'] = comparison['comparison_digest']
    ticket['delivery_digest'] = content_digest({k: v for k, v in ticket.items() if k != 'delivery_digest'})
    assert not all(r['passed'] for r in causal_comparison_checks(spec, {}))
