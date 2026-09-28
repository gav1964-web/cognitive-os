from copy import deepcopy
from pathlib import Path

import pytest

from runtime.architecture_decision_builder import build_architecture_decision
from runtime.technical_spec_builder import build_technical_spec
from runtime.upstream_role_handoff import frame_analysis
from runtime.upstream_task_contract import normalize_task_contract


@pytest.fixture
def inputs(tmp_path):
    (tmp_path / 'core.py').write_text('def average(values):\n    return sum(values) / len(values)\n')
    contract = {'schema_version': 'upstream_task_contract.v1', 'origin': 'user_supplied', 'change_kind': 'defect',
        'requirements': [{'id': 'EMPTY', 'statement': 'Return None for empty input.', 'targets': ['core.py:average'],
                          'acceptance_examples': [{'input': [], 'expected': None}]}], 'constraints': []}
    report = {'root': tmp_path.as_posix(), 'summary': {'root': tmp_path.as_posix()},
        'answers': {'3_capabilities': {'pure_transforms': [{'path': 'core.py', 'name': 'average'}]}}}
    return tmp_path, contract, report


def test_requirements_survive_to_spec_without_becoming_verified_design(inputs):
    root, contract, report = inputs
    analysis = frame_analysis(report, contract)
    adr = build_architecture_decision(goal='Repair empty input', project_report=analysis)
    spec = build_technical_spec(architecture_decision=adr)
    assert adr['chosen_option']['id'] == 'bounded_in_place_change'
    assert spec['requirements'][0]['statement'] == contract['requirements'][0]['statement']
    assert spec['requirements'][0]['origin'] == 'user_supplied'
    assert spec['requested_acceptance_criteria'][0]['example'] == {'input': [], 'expected': None}
    assert spec['requested_acceptance_criteria'][0]['execution_status'] == 'not_run'
    assert spec['task_handoff']['status'] == 'needs_design'
    assert spec['implementation_delta']['status'] == 'blocked'
    assert analysis['task_analysis']['causal_diagnosis'] == 'not_established'


def test_contradiction_blocks_architecture_and_spec(inputs):
    root, contract, report = inputs
    contract['constraints'] = [{'key': 'order', 'value': 'ascending'}, {'key': 'order', 'value': 'input'}]
    analysis = frame_analysis(report, contract)
    adr = build_architecture_decision(goal='Arrange', project_report=analysis)
    spec = build_technical_spec(architecture_decision=adr)
    assert analysis['task_analysis']['conflicting_constraints'] == ['order']
    assert adr['chosen_option']['id'] == 'clarify_before_change'
    assert adr['first_slice_contract']['targets'] == []
    assert spec['task_handoff']['status'] == 'needs_clarification'


def test_stale_source_observation_requires_new_analysis(inputs):
    root, contract, report = inputs
    analysis = frame_analysis(report, contract)
    (root / 'core.py').write_text('def average(values):\n    return None\n')
    adr = build_architecture_decision(goal='Repair', project_report=analysis)
    assert adr['task_design_status'] == 'needs_clarification'
    assert any('stale' in q['question'] for q in adr['open_questions'])


@pytest.mark.parametrize('target', ['../outside.py:read', 'core.py:missing', 'core.py', 'config.json:key'])
def test_unverified_target_never_becomes_ready(inputs, target):
    root, contract, report = inputs
    contract['requirements'][0]['targets'] = [target]
    result = frame_analysis(report, contract)
    assert result['task_analysis']['status'] == 'needs_clarification'
    assert result['task_analysis']['source_facts'] == []


def test_missing_acceptance_is_explicit_and_mandatory_requirements_not_downgraded(inputs):
    root, contract, report = inputs
    contract['requirements'].append({'id': 'PRESERVE', 'statement': 'Retain normal averages.',
                                   'targets': ['core.py:average']})
    adr = build_architecture_decision(goal='Repair', project_report=frame_analysis(report, contract))
    spec = build_technical_spec(architecture_decision=adr)
    assert all(r['priority'] == 'MUST' for r in spec['requirements'])
    assert {'requirement_id': 'PRESERVE', 'reason': 'acceptance_observation_missing'} in spec['task_handoff']['gaps']


def test_task_input_and_source_are_not_mutated(inputs):
    root, contract, report = inputs
    old = deepcopy(contract)
    data = (root / 'core.py').read_bytes()
    analysis = frame_analysis(report, contract)
    analysis['task_contract']['requirements'][0]['statement'] = 'Changed'
    assert contract == old
    assert (root / 'core.py').read_bytes() == data


@pytest.mark.parametrize('mutation', ['duplicate', 'tamper', 'missing_origin', 'too_many'])
def test_invalid_task_contract_rejected(inputs, mutation):
    _, contract, _ = inputs
    if mutation == 'duplicate':
        contract['requirements'] *= 2
    elif mutation == 'tamper':
        contract = normalize_task_contract(contract)
        contract['requirements'][0]['statement'] = 'Changed'
    elif mutation == 'missing_origin':
        del contract['origin']
    else:
        contract['requirements'] *= 33
    with pytest.raises(ValueError):
        normalize_task_contract(contract)
