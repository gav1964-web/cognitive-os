"""Native evidence distinguishes a fix, a wrong repair and underdetermined choices."""
from copy import deepcopy

import pytest

from runtime.stage_finalization_workspace import inventory
from runtime.upstream_causal_trials import compare_causal_candidates
from tests.runtime.test_native_failure_acceptance import replay_case, SOURCE, FIXED


def _candidate(source, ident, text):
    return {'id': ident, 'origin': 'training_rule_proposal',
            'source_sha256': inventory(source)['channel.py'], 'replacement_source': text}


def _run(tmp_path, replay_case, candidates):
    source, spec = replay_case
    return compare_causal_candidates(project=source,
        packet=spec['implementation_delta']['intent']['failure_evidence_packet'],
        candidates=candidates, work_dir=tmp_path, authorized=True)


def test_rejects_rebinding_and_selects_in_place_fix(tmp_path, replay_case):
    source, _ = replay_case
    before = inventory(source)
    wrong = SOURCE.replace('pass', 'self.pending = []')
    result = _run(tmp_path, replay_case, [_candidate(source, 'rebind', wrong), _candidate(source, 'mutate', FIXED)])
    assert [r['outcome'] for r in result['attempts']] == ['contradicted_by_targeted_tests', 'supported_by_targeted_tests']
    assert result['selected_candidate_id'] == 'mutate'
    assert result['status'] == 'selected_for_regression'
    assert result['root_cause_uniquely_proven'] is False
    assert result['complete_native_regression'] == 'still_required'
    assert before == inventory(source)
    from runtime.upstream_causal_review import causal_comparison_checks
    packet = replay_case[1]['implementation_delta']['intent']['failure_evidence_packet']
    selected = result['attempts'][1]
    spec = {'implementation_delta': {'intent': {'causal_comparison': result,
        'failure_evidence_packet': packet, 'operator_id': selected.get('operator_id')}}}
    assert all(r['passed'] for r in causal_comparison_checks(spec, selected['evidence']))
    changed = {**selected['evidence'], 'patched_inventory_digest': 'another-green-patch'}
    assert not all(r['passed'] for r in causal_comparison_checks(spec, changed))
    spec['implementation_delta']['intent']['causal_comparison'] = {**result, 'selected_candidate_id': 'rebind'}
    assert not all(r['passed'] for r in causal_comparison_checks(spec, selected['evidence']))


def test_two_passing_patches_require_discriminating_evidence(tmp_path, replay_case):
    source, _ = replay_case
    second = SOURCE.replace('pass', 'self.pending.clear()')
    result = _run(tmp_path, replay_case, [_candidate(source, 'slice', FIXED), _candidate(source, 'clear', second)])
    assert result['status'] == 'ambiguous'
    assert result['selected_candidate_id'] is None
    assert all(r['outcome'] == 'supported_by_targeted_tests' for r in result['attempts'])


def test_authorization_and_packet_checked_before_any_probe(tmp_path, replay_case):
    source, spec = replay_case
    packet = deepcopy(spec['implementation_delta']['intent']['failure_evidence_packet'])
    args = dict(project=source, packet=packet, candidates=[_candidate(source, 'fix', FIXED)], work_dir=tmp_path / 'runs')
    with pytest.raises(ValueError, match='authorization'):
        compare_causal_candidates(**args)
    packet['project_inventory_digest'] = 'stale'
    with pytest.raises(ValueError, match='packet'):
        compare_causal_candidates(**args, authorized=True)
    assert not (tmp_path / 'runs').exists()


def test_noop_and_duplicates_do_not_establish_unique_mechanism(tmp_path, replay_case):
    source, _ = replay_case
    result = _run(tmp_path, replay_case, [_candidate(source, 'noop', SOURCE), _candidate(source, 'same', SOURCE)])
    assert result['selected_candidate_id'] is None
    assert result['status'] == 'inconclusive'


def test_unknown_training_pattern_cannot_keep_execution_authority(tmp_path):
    from pathlib import Path
    from runtime.upstream_causal_selection import validate_diagnosis_proposals
    diagnosis = {'issues': [{'failure_specific_reducer_required': True, 'allowed_operator_ids': ['old'],
                            'training_replay_authority': {'status': 'explicitly_authorized'},
                            'repair_design': {'execution_authority': 'explicit_training_replay'}}]}
    result = validate_diagnosis_proposals(diagnosis, project=tmp_path, root=Path.cwd(), authorized=True)
    issue = result['issues'][0]
    assert issue['allowed_operator_ids'] == []
    assert 'training_replay_authority' not in issue
    assert issue['repair_design']['execution_authority'] is False
    assert issue['causal_feedback']['role'] == 'analyzer'
    assert diagnosis['issues'][0]['allowed_operator_ids'] == ['old']
