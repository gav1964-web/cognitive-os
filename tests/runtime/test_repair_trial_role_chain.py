"""A scripted response tests the full engineering chain, not model competence."""
import json
import sys
from copy import deepcopy
from pathlib import Path
import pytest

from runtime.local_inference import LocalInferenceConfig
from runtime.project_development import run_project_development, load_project_development_policy
from runtime.project_native_failure_binding import _interpret_pytest_result
from runtime.repair_target_nomination import trace_failure_methods, nomination_context, validate_nomination
from runtime.repair_trial_binding import build_repair_trial_packet
from runtime.stage_finalization_workspace import inventory
from tests.runtime.test_repair_target_nomination import prepare, proposal
from tests.runtime.test_repair_trial_binding import provider


@pytest.mark.parametrize('use_observations,route', [
    (False, 'hypothesis'), (True, 'hypothesis'), (True, 'direct'),
    ('native', 'direct'), ('native', 'hypothesis')])
def test_nominated_method_reaches_native_regression_and_final_reviewer(tmp_path, monkeypatch, use_observations, route):
    (tmp_path / 'project').mkdir()
    (tmp_path / 'project/pyproject.toml').write_text(
        "[project]\nname='repair-trial-library'\nversion='0.1.0'\n", encoding='utf-8')
    project, observation = prepare(tmp_path)
    trace = trace_failure_methods(project=project, packet=observation, work_dir=tmp_path / 'trace', authorized=True)
    context = nomination_context(project=project, packet=observation, trace=trace)
    nomination = validate_nomination(proposal(context), project=project, packet=observation, trace=trace, context=context)
    bundle = {'nomination': nomination, 'trace': trace, 'context': context}
    packet = build_repair_trial_packet(project=project, observation=observation, bundle=bundle)
    records = []
    for i in range(2):
        output = (tmp_path / f'intake-{i}/output.txt').read_text(encoding='utf-8')
        records.append({**_interpret_pytest_result(project, 1, output, {}), 'exit_code': 1, 'output_tail': output})
    failure = {'target': observation['target'], 'failure_signature': observation['failure_signature'],
        'failing_nodeids': observation['failing_nodeids'], 'detail': observation['observed_failure'],
        'authority': 'failing_contract_test', 'failure_kind': 'test_failed'}
    calls = provider(monkeypatch, packet)
    from runtime.repair_branch_evidence import collect_branch_evidence
    branches = collect_branch_evidence(project=project, packet=packet, work_dir=tmp_path / 'branches', authorized=True)
    observations = None
    if use_observations == 'native':
        from runtime.native_repair_observations import collect_native_repair_observations
        observations = collect_native_repair_observations(project, packet, tmp_path/'observations',
            authorized=True, method_fields={packet['target']: []})
    elif use_observations:
        from runtime.repair_observations import collect_repair_observations
        observations = collect_repair_observations(project, packet, tmp_path/'observations', authorized=True)
    import runtime.project_development_llm_hypothesis as hypotheses
    old = hypotheses.call_json_chat
    def grounded(messages, config):
        response = old(messages, config)
        if use_observations:
            key = 'native_test_observations' if use_observations == 'native' else 'isolated_assertion_observations'
            assert json.loads(messages[1]['content'])['diagnostic_context'][key]['rows']
        response['reached_return_ids'] = [r['id'] for r in branches['facts']]
        contract = json.loads(messages[1]['content'])['assertion_contract']
        response['assertion_plan'] = [{'assertion_id': r['id'], 'behavior': 'Preserve the asserted public converter result.'}
                                      for r in contract['assertions']]
        return response
    monkeypatch.setattr(hypotheses, 'call_json_chat', grounded)
    from runtime.upstream_llm_trials import validate_llm_diagnosis_proposals
    from runtime.programmer_executor import run_programmer_executor
    monkeypatch.setattr('runtime.upstream_llm_trials.validate_llm_diagnosis_proposals',
        lambda *a, **kw: validate_llm_diagnosis_proposals(*a, **{**kw, 'root': tmp_path}))
    monkeypatch.setattr('runtime.project_development_experiment.run_programmer_executor',
        lambda **kw: run_programmer_executor(**{**kw, 'execution_base_dir': tmp_path / 'exec'}))
    policy = load_project_development_policy()
    policy['model_require_assertion_plan'] = True
    policy['model_proposal_route'] = route
    policy['native_failure_intake'].update(local_editable_install=False, python_executable=sys.executable,
        regression_targets=[], nested_pytest_plugins=[], timeout_seconds=20)
    before = inventory(project)
    result = run_project_development(root=Path(__file__).resolve().parents[2], project_dir=project,
        goal='Repair internal conversion while preserving existing public behavior.',
        run_role_chain=True, run_sandbox_experiment=True, authorize_training_replay=True,
        validate_causal_proposals=True, repair_nomination=bundle, repair_branch_evidence=branches,
        repair_observations=observations,
        llm_hypothesis_config=LocalInferenceConfig(base_url='http://example.invalid', model='scripted'),
        chain_case={'project_stratum': 'library_pure_transform',
                    'contract_failure_evidence': [failure], 'repetitions': records}, policy=policy)
    (tmp_path / 'role_run.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    assert calls == (['candidate'] if route == 'direct' else ['hypothesis', 'candidate'])
    assert result['status'] == 'experiment_validated', (result['role_chain_handoff'], result['experiment'])
    experiment = result['experiment']
    assert experiment['final_review']['recommendation'] == 'approve'
    assert all(experiment['checks'].values())
    ticket = result['decision']['selected_issue']['model_delivery']
    spec = result['role_artifacts']['technical_spec']
    assert spec['implementation_delta']['intent']['repair_grounding']['branch_digest'] == branches['branch_digest']
    assert ticket['target'] == packet['target']
    assert (Path(experiment['sandbox_project']) / 'core.py').read_bytes() == ticket['replacement_source'].encode('utf-8')
    assert inventory(project) == before
    # Removing grounding from both planning artifacts must not bypass the
    # selected candidate's binding, even though Spec and Plan agree with each other.
    from runtime.programmer_model_delivery import model_delivery_precheck
    intent = spec['implementation_delta']['intent']
    plan = {'implementation_delta': deepcopy(spec['implementation_delta'])}
    assert model_delivery_precheck(spec, plan) is None
    fields = ['branch_digest', 'reached_return_ids', 'reached_returns', 'assertion_contract']
    fields += ['proposal_route', 'request_context_digest'] if route == 'direct' else ['assertion_plan']
    for field in fields:
        bad_spec, bad_plan = deepcopy(spec), deepcopy(plan)
        for artifact in (bad_spec, bad_plan):
            artifact['implementation_delta']['intent']['repair_grounding'].pop(field)
        assert model_delivery_precheck(bad_spec, bad_plan) == 'model_delivery_spec_plan_invalid'
    selected = next(a for a in intent['causal_comparison']['attempts']
                    if a['id'] == intent['model_delivery']['candidate_id'])
    assert selected['provenance']['repair_audit']['execution_authorized'] is False
    if route == 'direct':
        assert selected['provenance']['proposal_route'] == 'direct'
        assert 'hypothesis_response_digest' not in selected['provenance']
        assert 'assertion_plan' not in selected['provenance']['repair_design']
