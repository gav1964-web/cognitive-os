from copy import deepcopy

import pytest

from runtime.repair_branch_evidence import collect_branch_evidence, validate_branch_evidence
from runtime.narrow_type_evidence_binding import content_digest
from tests.runtime.test_repair_trial_binding import repair_case, evidence


@pytest.fixture
def branches(repair_case, tmp_path):
    project, _, _, packet = repair_case
    proof = collect_branch_evidence(project=project, packet=packet, work_dir=tmp_path / 'trace', authorized=True)
    return project, packet, proof


def test_reached_return_is_source_bound_and_advisory(branches):
    project, packet, proof = branches
    assert proof['facts'] == [{'id': 'R1', 'line': 7, 'source': "return 'broken'"}]
    assert proof['execution_authorized'] is False
    validate_branch_evidence(project, packet, proof)


@pytest.mark.parametrize('change', ['return', 'line', 'hash', 'exception'])
def test_modified_branch_proof_is_rejected(branches, change):
    project, packet, proof = branches
    changed = deepcopy(proof)
    if change == 'return':
        changed['facts'][0]['source'] = "return 'fixed'"
    elif change == 'line':
        changed['executed_lines'] = [99999]
    elif change == 'hash':
        changed['file_sha256'] = '0' * 64
    else:
        trace = changed['trace']
        for p in trace['probes']:
            p['trace']['rows'][0]['invocations'][0]['repair_line_events'] = [['exception', 7]]
        trace['trace_digest'] = content_digest({k:v for k,v in trace.items() if k!='trace_digest'})
    changed['branch_digest'] = content_digest({k:v for k,v in changed.items() if k!='branch_digest'})
    with pytest.raises(ValueError):
        validate_branch_evidence(project, packet, changed)
