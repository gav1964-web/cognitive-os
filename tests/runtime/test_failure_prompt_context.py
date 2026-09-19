"""Keep complete parameterized evidence and explicit hypothesis diagnostics."""
import json

import pytest

from runtime.project_failure_prompt_context import test_source_groups as group_sources
from runtime.project_failure_evidence_packet import _test_source
from runtime.project_development_llm_hypothesis import _evidence_envelope, _messages, build_llm_failure_hypothesis
from runtime.upstream_llm_candidates import candidate_messages
from runtime.upstream_llm_candidates import build_model_candidates
from tests.runtime.test_project_development_llm_hypothesis import _issue, _project, _config, _payload


def test_parameterized_sources_reach_both_prompts_once_with_all_nodeids(tmp_path):
    (tmp_path / 'test_example.py').write_text(
        'import pytest\n@pytest.mark.parametrize("value, expected", [(0, "zero"), (7, "seven")])\n'
        'def test_format(value, expected):\n    assert format_value(value) == expected\n')
    rows = [_test_source(tmp_path, f'test_example.py::test_format[case-{i}]') for i in range(8)]
    packet = {'target': 'example.py:format_value', 'test_sources': rows}
    envelope = _evidence_envelope(target=packet['target'], failure={'failing_nodeids':[r['nodeid'] for r in rows]},
        source='def format_value(value):\n    return value\n', packet=packet)
    proposal = json.loads(candidate_messages(packet, {'causal_hypothesis':{},'repair_design':{}},
        'def format_value(value):\n    return value\n')[1]['content'])
    for context in (envelope, proposal):
        assert len(context['test_sources']) == 1
        group = context['test_sources'][0]
        assert group['nodeids'] == [r['nodeid'] for r in rows]
        assert '@pytest.mark.parametrize' in group['excerpt'] and '(7, "seven")' in group['excerpt']
        assert group['excerpt_complete'] is True
        assert 'assert format_value(value) == expected' in group['excerpt']


def test_same_path_different_source_is_not_merged():
    first = {'path':'test_x.py','nodeid':'test_x.py::test_a','excerpt':'assert a','sha256':'a'}
    second = {**first,'nodeid':'test_x.py::test_b','excerpt':'assert b','sha256':'b'}
    assert len(group_sources([first, second])) == 2


def test_large_parameter_source_is_marked_incomplete(tmp_path):
    (tmp_path / 'test_x.py').write_text('@parametrize("value", [' + ','.join(map(str,range(2000)))
        + '])\ndef test_x(value):\n    assert value\n')
    row = _test_source(tmp_path, 'test_x.py::test_x[0]')
    assert row['excerpt_complete'] is False
    assert len(row['excerpt']) == 5000


def test_schema_describes_confidence_without_setting_an_answer():
    message = _messages({'target':'example.py:fn','failure_signature':'signature'})[0]['content']
    schema = json.loads(message.split('JSON Schema: ',1)[1])
    assert schema['properties']['confidence']['type'] == 'number'
    assert 'default' not in schema['properties']['confidence']
    assert set(schema['required']) == set(_payload())
    assert schema['properties']['target']['const'] == 'example.py:fn'


def test_module_imports_are_rejected_without_rewriting_the_model_answer():
    code = 'import math\ndef fn(x):\n    return math.floor(x)\n'
    payload = {'candidates':[{'id':'one','replacement_source':code,'reason':'use floor'}]}
    with pytest.raises(ValueError,match='replacement_must_be_single_function'):
        build_model_candidates(payload,source='def fn(x):\n    return x\n',
            packet={'target':'example.py:fn'},advisory={})
    assert payload['candidates'][0]['replacement_source'] == code


@pytest.mark.parametrize('feedback_size,invoked', [(13000,True),(25000,False)])
def test_requested_retry_uses_bounded_counterexample_envelope(tmp_path,monkeypatch,feedback_size,invoked):
    issue=_issue()
    feedback={'examples':[{'native_output':'x'*feedback_size}]}
    issue.update(native_counterexamples=feedback,prior_native_comparison={},
                 requested_task_contract={'contract_digest':'task'})
    monkeypatch.setattr('runtime.repair_counterexamples.native_counterexamples',lambda *args:feedback)
    calls=[]
    def chat(messages,*,config):
        envelope=json.loads(messages[1]['content'])
        assert envelope['native_counterexamples']==feedback
        assert envelope['task_contract_digest']=='task'
        calls.append(envelope)
        return _payload()
    result=build_llm_failure_hypothesis(issue=issue,project_dir=_project(tmp_path),config=_config(),chat=chat)
    assert bool(calls)==invoked
    if not invoked:assert 'counterexample_prompt_budget_exceeded' in result['errors']


@pytest.mark.parametrize('size,invoked', [(13000,True),(25000,False)])
def test_requested_contract_keeps_explicit_bounded_context(tmp_path,size,invoked):
    issue=_issue();issue['requested_task_contract']={'contract_digest':'task','requirements':'x'*size}
    calls=[]
    def chat(messages,*,config):
        envelope=json.loads(messages[1]['content'])
        assert envelope['task_contract']['requirements']=='x'*size
        calls.append(envelope)
        return _payload()
    result=build_llm_failure_hypothesis(issue=issue,project_dir=_project(tmp_path),config=_config(),chat=chat)
    assert bool(calls)==invoked
    if not invoked:assert 'requested_hypothesis_prompt_budget_exceeded' in result['errors']


@pytest.mark.parametrize('confidence', [0.0, 0.4])
def test_rejected_diagnosis_remains_visible_without_execution_authority(tmp_path, monkeypatch, confidence):
    payload = {**_payload(), 'confidence':confidence}
    monkeypatch.setattr('runtime.project_development_llm_hypothesis.call_json_chat',lambda *a,**k:payload)
    result = build_llm_failure_hypothesis(issue=_issue(),project_dir=_project(tmp_path),config=_config())
    assert result['status'] == 'rejected' and 'confidence_below_threshold' in result['errors']
    assert result['rejected_response_diagnostics']['confidence'] == confidence
    assert result['rejected_response_diagnostics']['mechanism'] == payload['mechanism']
    assert result['execution_authorized'] is False
    assert 'repair_design' not in result and 'causal_hypothesis' not in result
