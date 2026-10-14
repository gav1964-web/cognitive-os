"""A replay must preserve the failure set that was signed during intake."""
import sys
from pathlib import Path

import pytest

from runtime.native_failure_acceptance import _probe, build_native_acceptance, run_native_acceptance
from runtime.project_failure_evidence_packet import build_failure_evidence_packet
from runtime.project_native_failure_binding import _interpret_pytest_result
from runtime.stage_finalization_workspace import inventory, snapshot


def test_five_parametrized_failures_survive_paired_acceptance(tmp_path):
    source = tmp_path / 'source'
    (source / 'tests').mkdir(parents=True)
    (source / 'lookup.py').write_text('def lookup(value):\n    return value\n')
    (source / 'tests/test_lookup.py').write_text(
        'import pytest\nfrom lookup import lookup\n'
        '@pytest.mark.parametrize("value", range(5))\n'
        'def test_lookup(value):\n    assert lookup(value) is None\n')
    nodes = [f'tests/test_lookup.py::test_lookup[{i}]' for i in range(5)]
    repetitions = []
    for index in range(2):
        probe = _probe(source, tmp_path / f'intake-{index}', nodes, [], 20, Path(sys.executable))
        row = _interpret_pytest_result(source, probe['returncode'], Path(probe['output']).read_text(), {})
        repetitions.append(row)
    assert repetitions[0]['failing_nodeids'] == nodes
    target = 'lookup.py:lookup'
    packet = build_failure_evidence_packet(project_dir=source, failure={
        'target': target, 'failure_signature': repetitions[0]['failure_signature'], 'failing_nodeids': nodes,
    }, chain_case={'repetitions': repetitions})
    spec = {'contract_mode': 'failure_repair', 'implementation_delta': {'intent': {'failure_evidence_packet': packet}},
            'acceptance_criteria': [{'id': f'AC-FAILURE-REPLAY-{i:03}'} for i in range(5)]}
    contract = build_native_acceptance(spec, target)
    assert contract['status'] == 'ready'
    patched = tmp_path / 'patched'
    snapshot(source, patched, inventory(source))
    (patched / 'lookup.py').write_text('def lookup(value):\n    return None\n')
    result = run_native_acceptance(source_project=source, patched_project=patched,
                                   contract=contract, work_dir=tmp_path / 'acceptance')
    assert result['status'] == 'passed', result
    assert result['summary']['replayed_test_count'] == 5


@pytest.mark.parametrize('nodes', [
    [f'tests/test_case.py::test_case[{i}]' for i in range(9)],
    ['tests/test_case.py::test_case[' + 'a' * 1024 + ']'],
])
def test_truncated_failure_identity_cannot_qualify(tmp_path, nodes):
    output = 'E AssertionError\n' + '\n'.join('FAILED ' + node + ' - AssertionError' for node in nodes)
    result = _interpret_pytest_result(tmp_path, 1, output, {})
    assert result['status'] == 'unclassified_failure'
    assert result['failure_signature'] is None
    assert result['environment_reason'] == 'failure_identity_exceeds_replay_bounds'


def test_packet_rejects_more_than_eight_failures(tmp_path):
    (tmp_path / 'lookup.py').write_text('def lookup(value):\n    return value\n')
    (tmp_path / 'test_lookup.py').write_text('def test_lookup():\n    assert False\n')
    target = 'lookup.py:lookup'
    row = {'failure_signature': 'signature', 'leaf_production_target': target, 'exit_code': 1,
           'output_tail': 'E AssertionError: complete failure observation for missing value'}
    packet = build_failure_evidence_packet(project_dir=tmp_path, failure={
        'target': target, 'failure_signature': 'signature',
        'failing_nodeids': [f'test_lookup.py::test_lookup[{i}]' for i in range(9)],
    }, chain_case={'repetitions': [row, row]})
    assert packet['status'] == 'partial'
    assert packet['checks']['failure_set_within_replay_limit'] is False
