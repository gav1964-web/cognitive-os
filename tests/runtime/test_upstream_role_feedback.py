from copy import deepcopy

import pytest

from runtime.upstream_role_feedback import build_upstream_feedback
from runtime.upstream_role_audit import audit_upstream_roles
from runtime.upstream_role_handoff import frame_analysis
from runtime.architecture_decision_builder import build_architecture_decision
from runtime.technical_spec_builder import build_technical_spec
from runtime.role_pipeline import run_role_pipeline


@pytest.fixture
def chain(tmp_path):
    (tmp_path / 'core.py').write_text('def identity(value):\n    return value\n')
    task = {'schema_version': 'upstream_task_contract.v1', 'origin': 'user_supplied', 'change_kind': 'feature',
            'requirements': [{'id': 'R1', 'statement': 'Preserve Unicode.', 'targets': ['core.py:identity']}]}
    analysis = frame_analysis({'root': str(tmp_path), 'summary': {'root': str(tmp_path)}, 'answers': {}}, task)
    adr = build_architecture_decision(goal='Preserve Unicode', project_report=analysis)
    spec = build_technical_spec(architecture_decision=adr)
    return analysis, adr, spec


def test_contradictory_observation_reopens_analysis_but_never_grants_execution(chain):
    analysis, adr, spec = chain
    fact = analysis['task_analysis']['source_facts'][0]
    observation = {**fact, 'outcome': 'contradicts', 'receipt_digest': 'sha256:' + 'a' * 64}
    feedback = build_upstream_feedback(analysis=analysis, architecture=adr, specification=spec, observations=[observation])
    assert {r['role'] for r in feedback['requests']} == {'analyzer', 'architect', 'spec_writer'}
    assert feedback['execution_authorized'] is False
    assert feedback['automatic_retry'] is False
    assert 'not independently verified' in feedback['observation_authority']


def test_stale_observation_is_rejected_and_retry_budget_is_bounded(chain):
    analysis, adr, spec = chain
    fact = analysis['task_analysis']['source_facts'][0]
    observation = {**fact, 'file_sha256': 'wrong', 'outcome': 'supports', 'receipt_digest': 'sha256:' + 'b' * 64}
    args = {'analysis': analysis, 'architecture': adr, 'specification': spec}
    first = build_upstream_feedback(**args, observations=[observation])
    assert first['accepted_observations'] == []
    assert first['rejected_observations'] == [observation]
    second = build_upstream_feedback(**args, previous=first)
    third = build_upstream_feedback(**args, previous=second)
    assert third['status'] == 'retry_budget_exhausted'
    with pytest.raises(ValueError):
        build_upstream_feedback(**args, previous={**first, 'contract_digest': 'other'})


def test_spec_carries_diagnostic_design_without_promoting_its_authority(chain):
    analysis, adr, _ = chain
    design = {'steps': ['Retain original string.'], 'origin': 'assistant_supplied_diagnostic_input'}
    adr['design_proposal'] = design
    spec = build_technical_spec(architecture_decision=adr)
    assert spec['implementation_design_proposal'] == design
    assert spec['implementation_delta']['status'] == 'blocked'
    assert spec['task_handoff']['execution_authorized'] is False


def test_audit_never_turns_ok_or_preserved_requirements_into_quality_score(chain):
    analysis, adr, spec = chain
    result = audit_upstream_roles(task=analysis['task_contract'], analysis=analysis, architecture=adr, specification=spec)
    assert result['checks']['requirements_preserved']
    assert all(r['quality_score'] is None for r in result['roles'].values())
    assert not result['independent_judge']
    broken = deepcopy(spec)
    broken['requirements'][0]['statement'] = 'Different requirement'
    result = audit_upstream_roles(task=analysis['task_contract'], analysis=analysis, architecture=adr, specification=broken)
    assert not result['checks']['requirements_preserved']


def test_requested_change_cannot_get_final_review_by_forging_a_ready_label(chain):
    from runtime.review_findings_conformance import conformance_checks
    _, _, spec = chain
    spec['task_handoff'].update(status='ready', execution_authorized=True)
    spec['implementation_delta']['status'] = 'ready'
    rows = conformance_checks(spec, {}, {}, {}, {})
    row = next(r for r in rows if r['code'] == 'requested_change_design_verified')
    assert row['passed'] is False


@pytest.mark.parametrize('flags', [{'run_executor': True}, {'run_transform': True}, {'force_transform': True}, {'mode': 'greenfield'}])
def test_planning_contract_does_not_authorize_source_execution(tmp_path, flags):
    with pytest.raises(ValueError, match='design_validation'):
        run_role_pipeline(root=tmp_path, project_dir=tmp_path, goal='Change', task_contract={}, **flags)
