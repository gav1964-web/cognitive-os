"""The final Reviewer needs matching native acceptance and full regression."""
import pytest

from runtime.native_failure_acceptance import FORMAT, REQUIRED_CHECKS
from runtime.narrow_type_evidence_binding import content_digest
from runtime.review_findings_conformance import conformance_checks


def _review_inputs():
    target = 'pkg/service.py:run'
    contract = {'format': FORMAT, 'status': 'ready', 'target': target,
                'obligations': [{'id': 'AC-1', 'target': target}]}
    contract['contract_digest'] = content_digest(contract)
    inventory_digest = content_digest({'pkg/service.py': 'controlled-fixture'})
    acceptance = {'status': 'passed', 'format': FORMAT, 'patched_inventory_digest': inventory_digest,
        'contract_digest': contract['contract_digest'], 'summary': {
            'signal_strength': 'native_failure_replay', 'passed': True,
            'replayed_test_count': 1, 'native_replay_targets': [target],
            'native_replay_checks': dict.fromkeys(REQUIRED_CHECKS, True)}}
    return ({'contract_mode': 'failure_repair'}, {}, {'executable_acceptance': contract},
            {'status': 'ok', 'post_regression_source_check': {'status': 'passed',
             'accepted_inventory_digest': inventory_digest, 'current_inventory_digest': inventory_digest},
             'project_native_verification': {
                'status': 'passed', 'targeted_replay': {'status': 'passed'},
                'regression_suite': {'status': 'passed'}}}, acceptance)


@pytest.mark.parametrize('failure', ['result_digest', 'plan_digest', 'format', 'missing_result',
                                   'target', 'checks', 'missing_regression', 'regression_failed',
                                   'source_mutated', 'source_digest', 'missing_inventory'])
def test_final_reviewer_rejects_mismatched_or_incomplete_native_evidence(failure):
    spec, plan, tests, result, acceptance = _review_inputs()
    if failure == 'result_digest':
        acceptance['contract_digest'] = 'other'
    elif failure == 'plan_digest':
        tests['executable_acceptance']['obligations'].clear()
    elif failure == 'format':
        acceptance['format'] = 'other'
    elif failure == 'missing_result':
        acceptance = {}
    elif failure == 'target':
        acceptance['summary']['native_replay_targets'] = ['other.py:call']
    elif failure == 'checks':
        acceptance['summary']['native_replay_checks']['source_packet_current'] = False
    elif failure == 'missing_regression':
        result.pop('project_native_verification')
    elif failure == 'regression_failed':
        result['project_native_verification']['regression_suite']['status'] = 'failed'
    elif failure == 'source_mutated':
        result['post_regression_source_check']['status'] = 'failed'
    elif failure == 'source_digest':
        result['post_regression_source_check']['current_inventory_digest'] = 'different'
    elif failure == 'missing_inventory':
        acceptance.pop('patched_inventory_digest')
    checks = conformance_checks(spec, plan, tests, result, acceptance)
    assert any(not row['passed'] for row in checks if row['code'].startswith('native_'))


def test_planning_review_and_complete_execution_review_are_distinct():
    spec, plan, tests, result, acceptance = _review_inputs()
    for test_result, evidence in [({}, {}), (result, acceptance)]:
        checks = [row for row in conformance_checks(spec, plan, tests, test_result, evidence)
                  if row['code'].startswith('native_')]
        assert checks and all(row['passed'] for row in checks)
