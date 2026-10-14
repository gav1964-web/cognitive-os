"""Native regression must not mask rejected source-bound acceptance evidence."""
import pytest

from runtime.native_failure_acceptance import FORMAT, REQUIRED_CHECKS
from runtime.project_development import load_project_development_policy
from runtime.project_development_experiment import _experiment_artifact, _reassessment, _validated_memory

TARGET = 'pkg/service.py:run'


def _inputs():
    acceptance = {'status': 'passed', 'format': FORMAT, 'summary': {
        'signal_strength': 'native_failure_replay', 'passed': True,
        'replayed_test_count': 1, 'native_replay_targets': [TARGET],
        'native_replay_checks': dict.fromkeys(REQUIRED_CHECKS, True),
    }}
    return {
        'result': {'status': 'ok', 'source_code_changes': False},
        'patch': {'artifact_type': 'PatchPackage', 'status': 'prepared',
                  'patches': [{'file': 'pkg/service.py', 'kind': 'repair'}]},
        'test_result': {'status': 'ok', 'summary': {'failed': 0},
                        'executable_acceptance_result': acceptance},
        'native_verification': {'status': 'passed', 'targeted_replay': {'status': 'passed'},
                                'regression_suite': {'status': 'passed'}},
        'stub_admission': {'status': 'passed'}, 'admission': {'status': 'admitted'},
        'before': 'same', 'after': 'same',
        'decision': {'selected_issue': {'issue_id': 'ISSUE-1', 'rule_id': 'weak_contracts',
                    'failure_specific_reducer_required': True, 'affected_targets': [TARGET]}},
        'policy': load_project_development_policy(),
    }


@pytest.mark.parametrize('failure', ['failed', 'missing', 'generic', 'target', 'stale_packet',
                                   'changed_tests', 'executor', 'test_result', 'regression', 'aggregate'])
def test_green_native_suite_cannot_override_acceptance_or_execution_failure(failure):
    inputs = _inputs()
    acceptance = inputs['test_result']['executable_acceptance_result']
    if failure == 'failed':
        acceptance['status'] = 'failed'
    elif failure == 'missing':
        del inputs['test_result']['executable_acceptance_result']
    elif failure == 'generic':
        acceptance['format'] = 'generic'
    elif failure == 'target':
        acceptance['summary']['native_replay_targets'] = ['other.py:run']
    elif failure == 'stale_packet':
        acceptance['summary']['native_replay_checks']['source_packet_current'] = False
    elif failure == 'changed_tests':
        acceptance['summary']['native_replay_checks']['patch_scope_preserved'] = False
    elif failure == 'executor':
        inputs['result']['status'] = 'failed'
    elif failure == 'test_result':
        inputs['test_result']['status'] = 'failed'
    elif failure == 'regression':
        inputs['native_verification']['regression_suite']['status'] = 'failed'
    elif failure == 'aggregate':
        inputs['native_verification']['status'] = 'failed'
    experiment = _experiment_artifact(**inputs)
    assert experiment['status'] == 'failed', experiment
    reassessment = _reassessment('evaluated', inputs['decision'], {'baseline_evidence': [TARGET]},
                                {'issues': []}, experiment, inputs['test_result'])
    assert reassessment['status'] == 'not_validated'
    assert _validated_memory(inputs['decision'], experiment, reassessment,
                             inputs['policy'])['status'] == 'not_promoted'


def test_valid_native_acceptance_and_full_regression_can_validate():
    inputs = _inputs()
    experiment = _experiment_artifact(**inputs)
    assert experiment['status'] == 'verified'
    reassessment = _reassessment('evaluated', inputs['decision'], {'baseline_evidence': [TARGET]},
                                {'issues': []}, experiment, inputs['test_result'])
    assert reassessment['status'] == 'validated'


def test_failed_experiment_cannot_be_resurrected_by_reassessment():
    inputs = _inputs()
    experiment = _experiment_artifact(**inputs)
    experiment['status'] = 'failed'
    reassessment = _reassessment('evaluated', inputs['decision'], {'baseline_evidence': [TARGET]},
                                {'issues': []}, experiment, inputs['test_result'])
    assert reassessment['status'] == 'not_validated'
