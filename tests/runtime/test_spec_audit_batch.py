"""Gather semantic and continuity issues together without waiving either gate."""
import json
from copy import deepcopy

import pytest

from runtime.feature_quality_chat import QualityChat
from runtime.feature_quality_draft import correction_feedback, draft_binding
from runtime.local_inference import LocalInferenceConfig
from tests.runtime.test_feature_development import spec
from tests.runtime.test_feature_quality import augment


def test_audit_reports_new_issue_in_same_pass_as_dropped_case(tmp_path):
    original = augment('spec_writer', spec())
    previous = deepcopy(original)
    previous['tests'].append({'path': 'tests/test_positive.py', 'content':
        'from engine import display\ndef test_positive():\n    assert display(3) == "3"\n'})
    first_issue = {'owner': 'spec_writer', 'reason': 'preserve positive input', 'evidence': 'display(3)'}
    second_issue = {'owner': 'spec_writer', 'reason': 'preserve zero', 'evidence': 'display(0)'}
    audits, drafts = [], []
    payload = {'goal': 'labels', 'sources': [], 'artifacts': {'architect': {'design': 'v1'}}}

    def transport(messages, *, config):
        request = json.loads(messages[1]['content'])
        if config.provider_label == 'quality:spec_auditor':
            audits.append(request)
            assert request['known_admission_issues'][0]['draft_case_continuity']['unexplained']
            assert request['prior_audit_issues'] == [first_issue]
            return {'decision': 'reject', 'issues': [second_issue]}
        drafts.append(request)
        if len(drafts) == 1:
            return original
        feedback = request['quality_contract_feedback']
        assert {'draft_case_continuity', 'acceptance_audit'} <= set().union(*(set(i) for i in feedback['issues']))
        assert feedback['prior_audit_issues'] == [first_issue, second_issue]
        return {'status': 'read', 'reads': []}

    q = QualityChat(transport, tmp_path)
    q.pending['spec_writer'] = {'binding': draft_binding(payload, 'spec_writer'),
        'feedback': correction_feedback(previous, [{'acceptance_audit': {
            'decision': 'reject', 'issues': [first_issue]}}])}
    result = q([{'role': 'system', 'content': 'write'}, {'role': 'user', 'content': json.dumps(payload)}],
               config=LocalInferenceConfig('http://unused', 'fake', provider_label='feature:spec_writer'))
    assert result['status'] == 'read' and len(audits) == 1 and len(drafts) == 2


@pytest.mark.parametrize('defect', ['syntax', 'frozen', 'continuity'])
def test_approval_cannot_waive_native_admission_issues(tmp_path, defect):
    original = augment('spec_writer', spec())
    audits = []

    def transport(messages, *, config):
        if config.provider_label == 'quality:spec_auditor':
            audits.append(json.loads(messages[1]['content']))
            return {'decision': 'approve'}
        value = deepcopy(original)
        if defect != 'continuity':
            value['tests'][0]['content'] += '\nsyntax (' if defect == 'syntax' else '\n# altered frozen file\n'
        return value

    q = QualityChat(transport, tmp_path)
    if defect == 'frozen':
        q.frozen = original['tests']
    payload = {'goal': 'labels', 'sources': [], 'artifacts': {'architect': {'design': 'v1'}}}
    if defect == 'continuity':
        prior = deepcopy(original)
        prior['tests'][0]['content'] += '\ndef test_zero():\n    assert display(0) == "0"\n'
        q.pending['spec_writer'] = {'binding': draft_binding(payload, 'spec_writer'),
            'feedback': correction_feedback(prior, ['repair boundary'])}
    with pytest.raises(ValueError, match='quality_role_correction_limit:spec_writer'):
        q([{'role': 'system', 'content': 'write'}, {'role': 'user', 'content': json.dumps(payload)}],
            config=LocalInferenceConfig('http://unused', 'fake', provider_label='feature:spec_writer'))
    assert len(audits) == (3 if defect == 'continuity' else 0)
    assert 'spec_writer' in q.pending


def test_required_native_witness_still_precedes_paid_audit(tmp_path):
    calls = []

    def transport(messages, *, config):
        calls.append(config.provider_label)
        assert config.provider_label == 'feature:spec_writer'
        return augment('spec_writer', spec())

    q = QualityChat(transport, tmp_path)
    q.spec_witness = lambda value: [{'rejected_candidate_witness': 'No distinguishing assertion'}]
    with pytest.raises(ValueError, match='quality_role_correction_limit:spec_writer'):
        q([{'role': 'system', 'content': 'write'}, {'role': 'user', 'content': json.dumps({
            'goal': 'labels', 'sources': [], 'artifacts': {'architect': {'design': 'v1'}}})}],
            config=LocalInferenceConfig('http://unused', 'fake', provider_label='feature:spec_writer'))
    assert calls == ['feature:spec_writer'] * 3


def test_missing_coverage_label_and_semantic_gaps_are_batched_without_waiver(tmp_path):
    drafts, audits = [], []
    value = augment('spec_writer', spec())
    value['case_plan'][-1]['kind'] = 'feature_control'  # Historical real confusion.
    def transport(messages, *, config):
        request = json.loads(messages[1]['content'])
        if config.provider_label == 'quality:spec_auditor':
            audits.append(request)
            assert 'case_plan lacks feature/preservation/boundary' in request['known_admission_issues']
            return {'decision': 'approve'}
        drafts.append(request)
        return deepcopy(value)
    q = QualityChat(transport, tmp_path)
    with pytest.raises(ValueError, match='quality_role_correction_limit:spec_writer'):
        q([{'role': 'system', 'content': 'spec'}, {'role': 'user', 'content': json.dumps({
            'goal': 'labels', 'sources': [], 'artifacts': {}})}],
            config=LocalInferenceConfig('http://unused', 'fake', provider_label='feature:spec_writer'))
    assert len(audits) == len(drafts) == 3
    assert 'case_plan lacks feature/preservation/boundary' in drafts[1]['quality_contract_feedback']['issues']


@pytest.mark.parametrize('role,requested,expected', [('spec_auditor',32768,8192),
    ('spec_auditor',None,8192),
    ('spec_auditor',2048,2048),('spec_writer',32768,32768),('programmer',32768,32768)])
def test_short_audit_response_cap_is_applied_before_transport_only(role,requested,expected,tmp_path):
    captured=[]
    def transport(messages,*,config):
        captured.append(config.max_output_tokens)
        return {'decision':'approve'}
    q=QualityChat(transport,tmp_path)
    cfg=LocalInferenceConfig('http://unused','fake',provider_label='quality:'+role,max_output_tokens=requested)
    q.call([{'role':'system','content':'s'},{'role':'user','content':'{}'}],cfg)
    assert captured==[expected] and cfg.max_output_tokens==requested
