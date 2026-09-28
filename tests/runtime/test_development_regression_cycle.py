"""Actual rejected delivery replay, plus bounded retry orchestration controls."""
import json
from copy import deepcopy
from pathlib import Path

import pytest

from runtime.development_regression_feedback import build_regression_feedback, feedback_messages
from runtime.development_regression_cycle import run_regression_cycle
from runtime.stage_finalization_workspace import inventory, snapshot
from runtime.narrow_type_evidence_binding import content_digest
from tests.runtime.test_model_candidate_delivery import _run_case


def test_method_indentation_does_not_change_rejected_function_identity():
    from runtime.development_regression_feedback import function_identity
    raw='    def method(self):\n        return 1\n'
    assert function_identity(raw)==function_identity('def method(self):\n    return 1\n')
    assert function_identity(raw)!=function_identity('def method(self):\n    return 2\n')
    assert raw.startswith('    def')


@pytest.fixture(scope='module')
def rejected(tmp_path_factory):
    project, result = _run_case(tmp_path_factory.mktemp('regression-delivery'),
        source='def invert(value: bool) -> bool:\n    return bool(value) and False\n', replacement='return True')
    assert result['status']=='needs_replanning'
    return project,result


def test_regression_is_replayed_on_both_versions_before_feedback(rejected,tmp_path):
    project,run=rejected
    before=inventory(project)
    feedback=build_regression_feedback(project,run,tmp_path/'feedback',authorized=True)
    assert feedback['status']=='verified' and all(feedback['checks'].values())
    assert inventory(project)==before
    assert feedback['probes'][0]['passing']==1
    assert all(p['returncode']==1 for p in feedback['probes'][1:])
    assert 'assert True is False' in feedback['native_output']
    messages=feedback_messages([{'role':'user','content':'original frozen task'}],feedback,project)
    assert messages[0]['content']=='original frozen task'
    assert json.loads(messages[-1]['content'])['verified_regression_feedback']['candidate_function']==feedback['candidate_function']
    assert feedback['semantic_diagnosis_verified'] is False


def test_preexisting_failure_is_not_a_new_regression(rejected,tmp_path):
    project,run=rejected
    altered=deepcopy(run)
    altered['experiment']['project_native_verification']['regression_suite']['failing_nodeids']=['tests/test_logic.py::test_false']
    feedback=build_regression_feedback(project,altered,tmp_path/'feedback',authorized=True)
    assert feedback['status']=='not_verified'
    assert not feedback['checks']['baseline_passes']
    with pytest.raises(ValueError,match='not_current'):
        feedback_messages([],feedback,project)


@pytest.mark.parametrize('kind',['source','candidate','ticket','unauthorized'])
def test_stale_or_unauthorized_input_cannot_inject_feedback(rejected,tmp_path,kind):
    project,run=rejected
    project_copy=tmp_path/'source'
    snapshot(project,project_copy,inventory(project))
    altered=deepcopy(run)
    if kind=='source':
        (project_copy/'logic.py').write_text('def invert(value):\n    return None\n')
    if kind=='candidate':
        candidate=tmp_path/'candidate'
        original=Path(run['experiment']['sandbox_project'])
        snapshot(original,candidate,inventory(original))
        (candidate/'logic.py').write_text('def invert(value):\n    return None\n')
        altered['experiment']['sandbox_project']=str(candidate)
    if kind=='ticket':
        altered['role_artifacts']['technical_spec']['implementation_delta']['intent']['model_delivery']['candidate_id']='forged'
    with pytest.raises(ValueError):
        build_regression_feedback(project_copy,altered,tmp_path/'feedback',authorized=kind!='unauthorized')
    assert not (tmp_path/'feedback').exists()


@pytest.fixture
def cycle_args(tmp_path):
    project=tmp_path/'source'
    project.mkdir()
    (project/'core.py').write_text('def run():\n    return False\n')
    return dict(root=tmp_path,project_dir=project,goal='repair',task_contract={},chain_case={},policy={},
        config=None,chat=lambda messages,**kw:{},work_dir=tmp_path/'artifacts/cycle',authorized=True)


def test_success_stops_without_unnecessary_model_retry(cycle_args,monkeypatch):
    calls=[]
    def run(**kw):
        calls.append(kw)
        return {'status':'experiment_validated'}
    monkeypatch.setattr('runtime.development_regression_cycle.run_project_development',run)
    report=run_regression_cycle(**cycle_args)
    assert len(calls)==1 and not report['automatic_retry']
    assert report['source_unchanged']


def test_non_regression_stop_is_not_retried(cycle_args,monkeypatch):
    monkeypatch.setattr('runtime.development_regression_cycle.run_project_development',lambda **kw:{'status':'controlled_stop'})
    report=run_regression_cycle(**cycle_args)
    assert len(report['attempts'])==1
    assert report['reason']=='verified_targeted_candidate_with_native_regression_required'


@pytest.mark.parametrize('failure', ['repeat','changed_source','budget_unknown'])
def test_failed_retry_cannot_silently_continue(cycle_args,monkeypatch,failure):
    calls=[]
    source='def run():\n    return True\n'
    from runtime.development_regression_feedback import function_identity
    def feedback(*a,**kw):
        return {'status':'verified','digest':'fixture-feedback','candidate_function_identity':function_identity(source)}
    def run(**kw):
        calls.append(kw)
        if len(calls)==1:
            return {'status':'needs_replanning'}
        if failure=='changed_source':
            (cycle_args['project_dir']/'core.py').write_text('def run():\n    return None\n')
        kw['model_chat']([],config=None)
        pytest.fail('must stop before an executor can receive the response')
    def chat(*a,**kw):
        if failure=='budget_unknown':
            raise ValueError('budget_unresolved_usage')
        return {'candidates':[{'replacement_source':source+'# only a comment changed\n'}]}
    monkeypatch.setattr('runtime.development_regression_cycle.run_project_development',run)
    monkeypatch.setattr('runtime.development_regression_cycle.build_regression_feedback',feedback)
    monkeypatch.setattr('runtime.development_regression_cycle.feedback_messages',lambda messages,*a:messages)
    cycle_args['chat']=chat
    with pytest.raises(ValueError):
        run_regression_cycle(**cycle_args)
    report=json.loads((cycle_args['work_dir']/'cycle.json').read_text(encoding='utf-8'))
    assert report['status']=='controlled_stop' and len(calls)==2


def test_model_spec_names_exact_delivery_and_normalizes_single_target(rejected):
    _,run=rejected
    spec=run['role_artifacts']['technical_spec']
    row=next(r for r in spec['requirements'] if r['id']=='REQ-FAILURE-REPAIR')
    ticket=spec['implementation_delta']['intent']['model_delivery']
    assert ticket['delivery_digest'] in row['statement']
    assert 'approved failure reducer' not in row['statement']
    assert row['source']=='ProjectDevelopmentDecision.model_delivery'


def test_nontraining_candidate_authority_never_claims_training_or_independence(tmp_path):
    _,run=_run_case(tmp_path,authorize_model_trial=True)
    assert run['status']=='experiment_validated'
    assert run['safety']['model_trial_authorized']
    assert not run['safety']['training_replay_authorized']
    assert run['safety']['training_replay_scope'] is None
    assert not run['safety']['automatic_kb_promotion']


def test_semantic_evaluator_recognizes_valid_ticket_but_not_forged_authority(rejected):
    from runtime.narrow_type_role_semantics import _concrete_spec_action
    _,run=rejected
    spec=run['role_artifacts']['technical_spec']
    target=spec['implementation_delta']['intent']['target_symbol']
    assert _concrete_spec_action(spec,target)
    forged=deepcopy(spec)
    forged['implementation_delta']['intent']['model_delivery']['candidate_id']='not-the-executed-candidate'
    assert not _concrete_spec_action(forged,target)
    missing=deepcopy(spec)
    missing['implementation_delta']['intent'].pop('model_delivery')
    assert not _concrete_spec_action(missing,target)
