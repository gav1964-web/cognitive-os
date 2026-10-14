"""Execute requested repair and preservation observations on unchanged native tests."""
import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from runtime.native_failure_acceptance import _probe
from runtime.project_failure_evidence_packet import build_failure_evidence_packet
from runtime.project_failure_causal_diagnosis import enrich_failure_diagnosis
from runtime.upstream_causal_selection import validate_diagnosis_proposals
from runtime.upstream_requested_change import prepare_requested_change, bind_requested_change, bind_requested_spec
from runtime.upstream_requested_review import requested_change_checks
from runtime.upstream_role_handoff import frame_analysis
from runtime.project_development_delta import development_delta_transform
from tests.runtime.test_programmer_mapping_descent_patch import SOURCE

ROOT = Path(__file__).resolve().parents[2]
TARGET = 'store.py:Store.lookup'
FAIL = 'tests/test_store.py::test_missing_descendant_returns_default'
KEEP = 'tests/test_store.py::test_existing_path_keeps_value'
BAD = 'tests/test_store.py::test_unrelated_requested_behavior'
TESTS = '''from store import Store
def store():
    value = Store()
    value.tree = {'app': {'host': 'localhost'}}
    return value
def test_missing_descendant_returns_default():
    sentinel = object()
    assert store().lookup('/app/host/missing', sentinel) is sentinel
def test_existing_path_keeps_value():
    assert store().lookup('/app/host') == 'localhost'
def test_unrelated_requested_behavior():
    assert store().lookup('/app/host') == 'new-value'
'''


def requirement(ident, nodeid, baseline):
    return {'id': ident, 'statement': ident, 'targets': [TARGET], 'acceptance_examples': [
        {'kind': 'native_test', 'nodeid': nodeid, 'expectation': 'passes', 'baseline_expectation': baseline}]}


@pytest.fixture(scope='module')
def case(tmp_path_factory):
    work = tmp_path_factory.mktemp('requested-change')
    project = work / 'project'
    (project / 'tests').mkdir(parents=True)
    (project / 'store.py').write_bytes(SOURCE.encode('utf-8'))
    (project / 'tests/test_store.py').write_text(TESTS, encoding='utf-8')
    repetitions = []
    for i in range(2):
        probe = _probe(project, work / f'intake-{i}', [FAIL], [], 10, Path(sys.executable))
        assert probe['returncode'] == 1
        repetitions.append({'failure_signature': probe['intake_signature'], 'exit_code': 1,
            'leaf_production_target': TARGET, 'production_targets': [TARGET],
            'output_tail': Path(probe['output']).read_text(encoding='utf-8')})
    failure = {'target': TARGET, 'failure_signature': repetitions[0]['failure_signature'], 'failing_nodeids': [FAIL]}
    packet = build_failure_evidence_packet(project_dir=project, failure=failure, chain_case={'repetitions': repetitions})
    diagnosis = {'issues': [{'failure_specific_reducer_required': True, 'affected_targets': [TARGET],
        'failure_evidence': [failure], 'failure_evidence_packet': packet, 'allowed_operator_ids': []}]}
    diagnosis = enrich_failure_diagnosis(diagnosis, project_dir=project, workspace_root=ROOT, authorize_training_replay=True)
    # Keep all runtime outputs in the test workspace while loading the actual maintained policy/KB.
    policy_root = work / 'cos'
    for name in ['config/patch_synthesis_policy.json', 'knowledge/role_knowledge/project_failure_causal_hypotheses.json']:
        dest = policy_root / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes((ROOT / name).read_bytes())
    diagnosis = validate_diagnosis_proposals(diagnosis, project=project, root=policy_root, authorized=True)
    assert diagnosis['issues'][0]['causal_comparison']['status'] == 'selected_for_regression'
    return project, policy_root, diagnosis


def _bound(case, requirements):
    project, root, diagnosis = case
    contract = {'schema_version': 'upstream_task_contract.v1', 'origin': 'assistant_authored_development_fixture',
                'change_kind': 'defect', 'requirements': requirements}
    analysis = frame_analysis({'root': str(project)}, contract)
    request = prepare_requested_change(analysis, project)
    return bind_requested_change(diagnosis, request, project=project, root=root)['issues'][0]


def test_explicit_repair_and_preservation_survive_to_executable_delta(case):
    issue = _bound(case, [requirement('REPAIR', FAIL, 'fails'), requirement('PRESERVE', KEEP, 'passes')])
    request = issue['requested_change']
    assert request['status'] == 'verified_for_regression', (request.get('reason'), request.get('acceptance', {}).get('checks'))
    assert request['acceptance']['checks']['baseline_expectations_met']
    spec = development_delta_transform({'selected_issue': issue}, {})({'artifact_type': 'TechnicalSpec'})
    assert spec['implementation_delta']['status'] == 'ready'
    assert 'executed_on_baseline_and_candidate' in spec['reasoning_provenance']['acceptance']
    from runtime.upstream_role_audit import audit_upstream_roles
    def authority_ok(value):
        return audit_upstream_roles(task=request['contract'], analysis={}, architecture={},
            specification=value)['checks']['no_unverified_design_authority']
    assert authority_ok(spec)
    forged = deepcopy(spec)
    forged['requested_change']['acceptance']['checks']['requested_tests_passed'] = False
    assert not authority_ok(forged)
    assert {r['id'] for r in spec['requirements']} >= {'REPAIR', 'PRESERVE'}
    assert all(r['passed'] for r in requested_change_checks(spec, {}))
    ids = {c['id'] for c in spec['acceptance_criteria']}
    assert all(i in ids for r in spec['requirement_traceability'] for i in r['acceptance_ids'])
    stale = deepcopy(spec)
    stale['requirement_traceability'][0]['acceptance_ids'] = ['OLD-PLANNING-ID']
    assert not all(r['passed'] for r in requested_change_checks(stale, {}))
    broken = deepcopy(spec)
    broken['requirements'][0]['statement'] = 'A different requirement'
    assert not all(r['passed'] for r in requested_change_checks(broken, {}))
    assert not all(r['passed'] for r in requested_change_checks(spec, {'patched_inventory_digest': 'different'}))


@pytest.mark.parametrize('requirements', [
    [requirement('REPAIR', FAIL, 'fails'), requirement('ADDITIONAL', BAD, 'fails')],
    [requirement('PRESERVE', FAIL, 'passes')],
    [{'id': 'UNBOUND', 'statement': 'Unbound', 'targets': [TARGET]}],
])
def test_unmet_or_unbound_requirement_revokes_prior_replay_authority(case, requirements):
    issue = _bound(case, requirements)
    assert issue['requested_change']['status'] == 'needs_clarification'
    assert issue['allowed_operator_ids'] == []
    assert 'training_replay_authority' not in issue
    spec = development_delta_transform({'selected_issue': issue}, {})({'artifact_type': 'TechnicalSpec'})
    assert spec['implementation_delta']['status'] == 'blocked'
    assert not all(r['passed'] for r in requested_change_checks(spec, {}))


def test_call_references_are_possible_not_a_complete_graph(tmp_path):
    from runtime.upstream_change_impact import analyze_change_impact
    (tmp_path / 'core.py').write_text('def read(x):\n    return x\ndef use(v):\n    return read(v)\n')
    result = analyze_change_impact(tmp_path, ['core.py:read'])
    assert result['possible_callers'][0]['line'] == 4
    assert result['possible_callers'][0]['target_resolution'] == 'static_binding'
    assert result['possible_callers'][0]['resolved_targets'] == ['core.py:read']
    assert not result['complete_call_graph']


def test_native_contract_requires_comparison_before_analysis(tmp_path):
    from runtime.project_development import run_project_development
    with pytest.raises(ValueError, match='causal_comparison'):
        run_project_development(root=tmp_path, project_dir=tmp_path, goal='change', task_contract={})


def test_requested_binding_preserves_the_first_failed_transition(case):
    project, root, diagnosis = case
    diagnosis = deepcopy(diagnosis)
    issue = diagnosis['issues'][0]
    issue['causal_comparison'] = {'status': 'not_compared'}
    issue['causal_feedback'] = {'role': 'analyzer', 'reason': 'requested_hypothesis_prompt_budget_exceeded',
                               'next_action': 'reduce_duplicate_context', 'automatic_retry': False}
    expected = deepcopy(issue['causal_feedback'])
    contract = {'schema_version': 'upstream_task_contract.v1', 'origin': 'assistant_authored_development_fixture',
                'change_kind': 'defect', 'requirements': [requirement('REPAIR', FAIL, 'fails')]}
    request = prepare_requested_change(frame_analysis({'root': str(project)}, contract), project)
    bound = bind_requested_change(diagnosis, request, project=project, root=root)['issues'][0]
    assert bound['causal_feedback'] == expected
    assert bound['requested_change']['execution_authorized'] is False
