"""Acceptance regressions guide correction, never restore rejected authority."""
from copy import deepcopy

import pytest

from runtime.development_regression_feedback import build_regression_feedback, feedback_messages
from tests.runtime.test_model_candidate_delivery import _run_case
from tests.runtime.test_model_requested_delivery import _contract, SOURCE, KEEP


@pytest.fixture(scope='module')
def rejected_request(tmp_path_factory):
    return _run_case(tmp_path_factory.mktemp('rejected-request'),source=SOURCE,
                     replacement='return bool(value) or True',task_contract=_contract())


def test_requested_preservation_failure_is_replayed_before_feedback(rejected_request,tmp_path):
    project, run = rejected_request
    before = deepcopy(run)
    feedback = build_regression_feedback(project,run,tmp_path/'feedback',authorized=True)
    assert feedback['status']=='verified' and feedback['failing_nodeids']==[KEEP]
    assert feedback['rejection_stage']=='requested_acceptance'
    assert feedback['delivery_digest'] is None
    assert feedback['acceptance_receipt_digest']
    assert feedback_messages([],feedback,project)
    assert run == before
    assert run['requested_change']['execution_authorized'] is False


@pytest.mark.parametrize('bad',['proof','source','candidate','unverified_baseline'])
def test_invalid_requested_feedback_is_blocked(rejected_request,tmp_path,bad):
    from runtime.stage_finalization_workspace import inventory,snapshot
    from runtime.narrow_type_evidence_binding import content_digest
    project, original = rejected_request
    run = deepcopy(original)
    project_copy = tmp_path/'source'
    snapshot(project,project_copy,inventory(project))
    issue = next(i for i in run['diagnosis']['issues'] if i.get('failure_specific_reducer_required'))
    request = issue['requested_change']
    proof = request['acceptance']
    if bad=='proof': proof['patched_inventory_digest']='forged'
    if bad=='source': (project_copy/'logic.py').write_text('def invert(value): return None\n')
    if bad=='candidate': issue['causal_comparison']['attempts'][0]['patched_project']=str(project_copy)
    if bad=='unverified_baseline':
        proof['checks']['baseline_expectations_met']=False
        proof['receipt_digest']=content_digest({k:v for k,v in proof.items() if k!='receipt_digest'})
        request['request_digest']=content_digest({k:v for k,v in request.items() if k!='request_digest'})
    with pytest.raises(ValueError):
        build_regression_feedback(project_copy,run,tmp_path/'feedback',authorized=True)
    assert not (tmp_path/'feedback').exists()
