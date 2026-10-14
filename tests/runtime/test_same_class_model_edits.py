"""A coherent two-method repair must be declared, bounded, replayed and preserved."""
from copy import deepcopy
from pathlib import Path

import pytest

from runtime.model_edit_scope import same_class_edit_scope,apply_related_replacements
from runtime.upstream_llm_candidates import _replacement

SOURCE='''class Engine:
    def __init__(self, value):
        self.value = int(value)
    def render(self):
        return self.value + 1
    def untouched(self):
        return "keep"
'''
TARGET='core.py:Engine.__init__'
PRIMARY='''def __init__(self, value):
    self.empty = value == ""
    self.value = 0 if self.empty else int(value)
'''
RELATED=[{'target':'core.py:Engine.render','replacement_source':
          'def render(self):\n    return 0 if self.empty else self.value + 1\n'}]


def test_scope_preserves_unrelated_method_and_rejects_extra_edits():
    scope=same_class_edit_scope(SOURCE,TARGET)
    first=_replacement(SOURCE,TARGET,PRIMARY)
    result=apply_related_replacements(SOURCE,first,TARGET,scope,['core.py:Engine.render'],RELATED)
    assert 'return "keep"' in result
    assert 'return 0 if self.empty' in result
    for rows in ([],RELATED*2,[{**RELATED[0],'target':'elsewhere.py:f'}]):
        with pytest.raises(ValueError):
            apply_related_replacements(SOURCE,first,TARGET,scope,['core.py:Engine.render'],rows)
    with pytest.raises(ValueError,match='scope_changed'):
        apply_related_replacements(SOURCE+'\n',first,TARGET,scope,['core.py:Engine.render'],RELATED)


def test_retry_identity_includes_sibling_behavior():
    from runtime.development_regression_feedback import candidate_identity
    different=[{**RELATED[0],'replacement_source':'def render(self):\n    return 1\n'}]
    assert candidate_identity(PRIMARY,RELATED)!=candidate_identity(PRIMARY,different)


def test_primary_and_related_interfaces_remain_fixed():
    scope=same_class_edit_scope(SOURCE,TARGET)
    bad=[{**RELATED[0],'replacement_source':'def render(self, extra):\n    return 0\n'}]
    with pytest.raises(ValueError,match='signature_mismatch'):
        apply_related_replacements(SOURCE,_replacement(SOURCE,TARGET,PRIMARY),TARGET,scope,['core.py:Engine.render'],bad)


@pytest.mark.parametrize('replan',[False,True])
def test_same_class_model_repair_runs_complete_role_and_native_chain(tmp_path,replan):
    import sys
    from runtime.native_failure_acceptance import _probe
    from runtime.local_inference import LocalInferenceConfig
    from runtime.project_native_failure_binding import _interpret_pytest_result
    from runtime.project_development_core import run_project_development
    from runtime.project_development_policy import load_project_development_policy
    project=tmp_path/'project';project.mkdir()
    (project/'core.py').write_text(SOURCE)
    (project/'pyproject.toml').write_text('[project]\nname="same-class-fixture"\nversion="0.1.0"\n')
    (project/'test_core.py').write_text('from core import Engine\ndef test_empty():\n    assert Engine("").render() == 0\ndef test_positive():\n    assert Engine("1").render() == 2\ndef test_zero():\n    assert Engine("0").render() == 1\n')
    nodes=['test_core.py::test_empty'];records=[]
    for index in range(2):
        probe=_probe(project,tmp_path/f'intake{index}',nodes,[],30,Path(sys.executable))
        text=Path(probe['output']).read_text(encoding='utf-8')
        records.append({**_interpret_pytest_result(project,probe['returncode'],text,{}),'exit_code':probe['returncode'],'output_tail':text})
    failure={'target':TARGET,'failure_signature':records[0]['failure_signature'],'failing_nodeids':nodes,
             'authority':'failing_contract_test','detail':records[0]['output_tail']}
    contract={'schema_version':'upstream_task_contract.v1','origin':'user_supplied','change_kind':'defect',
        'requirements':[{'id':'R','statement':'Empty text renders zero; retain nonempty conversion and zero-input behavior.',
            'targets':[TARGET],'acceptance_examples':[{'kind':'native_test','nodeid':nodes[0],'expectation':'passes','baseline_expectation':'fails'}]}]}
    calls=[]
    def chat(messages,*,config):
        calls.append(messages)
        if len(calls)==1 or replan and len(calls)==3:
            assert 'eligible_related_targets' in messages[1]['content']
            if len(calls)==3:
                assert 'candidate_validation_rejection' in messages[1]['content']
            return {'target':TARGET,'failure_signature':failure['failure_signature'],
                'mechanism':'The constructor rejects empty input and render always adds one to initialized state.',
                'repair_mechanism':'Track empty input in constructor and let render return zero only for that state.',
                'mutation_contract':{'precondition':'Empty string raises in int conversion.',
                    'change':'Coordinate constructor state and render result for empty text.',
                    'preserved_behavior':'Keep nonempty integer conversion and existing positive increment.'},
                'confidence':0.9,'residual_risks':['Verify zero text still renders one.'],
                'related_targets':['core.py:Engine.render']}
        assert 'additional_replacements' in messages[0]['content']
        replacements=deepcopy(RELATED)
        if replan and len(calls)==2:
            replacements[0]['replacement_source']='def render(self):\n    return self.value + 1\n'
        return {'candidates':[{'id':'coherent','replacement_source':PRIMARY,
            'additional_replacements':replacements,'reason':'Initialize and consume explicit empty-input state.'}]}
    policy=load_project_development_policy()
    policy.update(model_include_dependency_context=True,model_same_class_repairs=True)
    policy['model_native_counterexample_retries']=int(replan)
    policy['native_failure_intake'].update(local_editable_install=False,python_executable=sys.executable,
        regression_targets=['test_core.py'],timeout_seconds=30)
    result=run_project_development(root=Path(__file__).resolve().parents[2],project_dir=project,goal='Repair empty input',
        task_contract=contract,chain_case={'project_stratum':'library_pure_transform','contract_failure_evidence':[failure],'repetitions':records},policy=policy,
        llm_hypothesis_config=LocalInferenceConfig(base_url='http://unused.invalid',model='scripted'),model_chat=chat,run_role_chain=True,run_sandbox_experiment=True,
        validate_causal_proposals=True,authorize_model_trial=True)
    assert len(calls)==(4 if replan else 2)
    assert result['status']=='experiment_validated',result['decision']
    assert (project/'core.py').read_text()==SOURCE
    proof=result['decision']['selected_issue']['causal_comparison']['attempts'][0]['provenance']
    assert proof['planned_related_targets']==['core.py:Engine.render']
