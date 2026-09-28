"""Scripted models test cross-module role handoffs, not model quality."""
import json
import sys
from pathlib import Path

import pytest

from runtime.local_inference import LocalInferenceConfig
from runtime.project_development import run_project_development, load_project_development_policy
from runtime.project_native_failure_binding import _interpret_pytest_result
from runtime.stage_finalization_workspace import inventory
from tests.runtime.test_repair_function_nomination import prepare_functions, bundle_for


@pytest.mark.parametrize('generator', [True, False])
def test_cross_module_repair_reaches_spec_native_and_reviewer(tmp_path, monkeypatch, generator):
    project, observation = prepare_functions(tmp_path, generator=generator)
    bundle = bundle_for(project, observation, tmp_path)
    from runtime.repair_trial_binding import build_repair_trial_packet
    from runtime.repair_preservation import collect_preservation_evidence
    packet = build_repair_trial_packet(project=project, observation=observation, bundle=bundle)
    preservation = collect_preservation_evidence(project=project, packet=packet,
        nodeids=['tests/test_case.py::test_preserved'], work_dir=tmp_path / 'preservation', authorized=True)
    from runtime.native_repair_observations import collect_native_repair_observations
    observations = collect_native_repair_observations(project, packet, tmp_path/'state', authorized=True,
        source_files=['api.py','callbacks.py','dispatch.py'], preservation=preservation,
        method_fields={'callbacks.py:convert':['value']})
    calls = []

    def hypothesis(messages, config):
        envelope = json.loads(messages[-1]['content'])
        assert envelope['observed_target'] == 'api.py:render'
        assert envelope['target'] == 'callbacks.py:convert'
        state = envelope['diagnostic_context']['native_test_observations']
        assert state['state_projection'] == 'bounded_python_state.v1'
        assert [r['test_outcome'] for r in state['rows']] == ['failed','passed']
        assert {r['target'] for r in envelope['repair_call_context']['methods']} == {
            'api.py:render', 'callbacks.py:convert', 'dispatch.py:dispatch'}
        calls.append('hypothesis')
        return {'target': envelope['target'], 'failure_signature': envelope['failure_signature'],
            'mechanism': 'The callback produces the wrong value for the bad input while dispatch forwards it.',
            'repair_mechanism': 'Correct the bad input branch of the callback and preserve the good input branch.',
            'mutation_contract': {'precondition': 'The public API dispatches the bad input to the callback.',
                'change': 'Produce the expected fixed value only for that input.',
                'preserved_behavior': 'Keep callback registration, signature, iteration protocol and all other inputs unchanged.'},
            'confidence': 0.8, 'residual_risks': ['Full native regression must confirm preserved behavior.'],
            'preservation_plan': [{'case_id': r['id'], 'behavior': 'The good input still returns the unchanged good value.'}
                                  for r in envelope['preservation_context']['cases']]}

    def candidate(messages, config):
        calls.append('candidate')
        context = json.loads(messages[-1]['content'])
        assert context['design']['diagnostic_context']['native_test_observations']['state_projection'] == 'bounded_python_state.v1'
        return {'candidates': [{'id': 'callback', 'reason': 'Correct the failing branch without changing dispatch.',
            'replacement_source': 'def convert(value):\n    ' + ('yield ' if generator else 'return ') +
                                  "'fixed' if value == 'bad' else value\n"}]}

    monkeypatch.setattr('runtime.project_development_llm_hypothesis.call_json_chat', hypothesis)
    monkeypatch.setattr('runtime.upstream_llm_trials.call_json_chat', candidate)
    from runtime.upstream_llm_trials import validate_llm_diagnosis_proposals
    from runtime.programmer_executor import run_programmer_executor
    monkeypatch.setattr('runtime.upstream_llm_trials.validate_llm_diagnosis_proposals',
        lambda *a, **kw: validate_llm_diagnosis_proposals(*a, **{**kw, 'root': tmp_path}))
    monkeypatch.setattr('runtime.project_development_experiment.run_programmer_executor',
        lambda **kw: run_programmer_executor(**{**kw, 'execution_base_dir': tmp_path / 'exec'}))
    records = []
    for i in range(2):
        output = (tmp_path / f'intake-{i}/output.txt').read_text(encoding='utf-8')
        records.append({**_interpret_pytest_result(project, 1, output, {}), 'exit_code': 1, 'output_tail': output})
    failure = {'target': observation['target'], 'failure_signature': observation['failure_signature'],
        'failing_nodeids': observation['failing_nodeids'], 'detail': observation['observed_failure'],
        'authority': 'failing_contract_test', 'failure_kind': 'test_failed'}
    policy = load_project_development_policy()
    policy['native_failure_intake'].update(local_editable_install=False, python_executable=sys.executable,
        regression_targets=[], nested_pytest_plugins=[], timeout_seconds=20)
    before = inventory(project)
    result = run_project_development(root=Path(__file__).resolve().parents[2], project_dir=project,
        goal='Repair the callback through the observed public API while preserving other inputs.',
        run_role_chain=True, run_sandbox_experiment=True, authorize_training_replay=True,
        validate_causal_proposals=True, repair_nomination=bundle, repair_preservation=preservation,
        repair_observations=observations,
        llm_hypothesis_config=LocalInferenceConfig(base_url='http://example.invalid', model='scripted'),
        chain_case={'project_stratum': 'library_pure_transform',
                    'contract_failure_evidence': [failure], 'repetitions': records}, policy=policy)
    (tmp_path / 'role_run.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    assert calls == ['hypothesis', 'candidate']
    assert result['status'] == 'experiment_validated', (result['role_chain_handoff'], result['experiment'])
    assert result['experiment']['final_review']['recommendation'] == 'approve'
    assert all(result['experiment']['checks'].values())
    spec = result['role_artifacts']['technical_spec']
    grounding = spec['implementation_delta']['intent']['repair_grounding']
    assert grounding['preservation_evidence'] == preservation
    proof = spec['implementation_delta']['intent']['causal_comparison']['attempts'][0]['provenance']['repair_design']
    assert proof['diagnostic_context']['native_test_observations']['observations_digest'] == observations['observations_digest']
    assert grounding['preservation_plan'][0]['case_id'] == 'P001'
    from copy import deepcopy
    from runtime.programmer_model_delivery import model_delivery_precheck
    broken = deepcopy(spec)
    broken['implementation_delta']['intent']['repair_grounding'].pop('preservation_evidence')
    assert model_delivery_precheck(broken, {'implementation_delta': deepcopy(broken['implementation_delta'])}) == 'model_delivery_spec_plan_invalid'
    packet = spec['implementation_delta']['intent']['failure_evidence_packet']
    assert packet['target'] == 'callbacks.py:convert'
    assert packet['observation_packet'] == observation
    ticket = result['decision']['selected_issue']['model_delivery']
    assert (Path(result['experiment']['sandbox_project']) / 'callbacks.py').read_bytes() == ticket['replacement_source'].encode('utf-8')
    assert inventory(project) == before
