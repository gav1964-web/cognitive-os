"""Real paired runs: stateful fixtures survive handoff and cannot be weakened."""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from runtime.native_failure_acceptance import build_native_acceptance, run_native_acceptance, _probe
from runtime.narrow_type_evidence_binding import content_digest
from runtime.programmer_acceptance_gate import acceptance_covers_plan
from runtime.project_failure_evidence_packet import build_failure_evidence_packet, evidence_packet_digest
from runtime.stage_finalization_workspace import inventory, snapshot
from runtime.test_plan_builder import build_test_plan

TARGET = 'channel.py:Channel.close'
NODE = 'tests/test_channel.py::test_close_settles_pending'
SOURCE = '''class Channel:
    def __init__(self, pending):
        self.pending = pending

    def close(self):
        pass
'''
FIXED = SOURCE.replace('        pass', '        self.pending[:] = []')
TEST = '''import json
from pathlib import Path
from channel import Channel

def test_close_settles_pending():
    pending = json.loads(Path('tests/pending.json').read_text())
    channel = Channel(pending)
    channel.close()
    assert pending == []
'''


@pytest.fixture(scope='module')
def replay_case(tmp_path_factory):
    work = tmp_path_factory.mktemp('native-case')
    source = work / 'source'
    (source / 'tests').mkdir(parents=True)
    (source / 'channel.py').write_text(SOURCE)
    (source / 'tests/test_channel.py').write_text(TEST)
    (source / 'tests/pending.json').write_text('[1, 2]')
    repetitions = []
    for index in range(2):
        result = _probe(source, work / f'intake-{index}', [NODE], [], 10, Path(sys.executable))
        assert result['returncode'] == 1
        repetitions.append({
            'failure_signature': result['intake_signature'], 'exit_code': 1,
            'leaf_production_target': TARGET, 'production_targets': [TARGET],
            'output_tail': Path(result['output']).read_text(encoding='utf-8'),
        })
    packet = build_failure_evidence_packet(project_dir=source, failure={
        'target': TARGET, 'failure_signature': repetitions[0]['failure_signature'],
        'failing_nodeids': [NODE],
    }, chain_case={'repetitions': repetitions})
    assert packet['status'] == 'complete'
    spec = {'contract_mode': 'failure_repair',
            'implementation_delta': {'intent': {'failure_evidence_packet': packet}},
            'acceptance_criteria': [{'id': 'AC-FAILURE-REPLAY-001', 'source': TARGET}]}
    return source, spec


def _copies(tmp_path, replay_case):
    source, spec = replay_case
    baseline, patched = tmp_path / 'baseline', tmp_path / 'patched'
    snapshot(source, baseline, inventory(source))
    snapshot(source, patched, inventory(source))
    (patched / 'channel.py').write_text(FIXED)
    return baseline, patched, build_native_acceptance(spec, TARGET)


def _run(tmp_path, projects):
    baseline, patched, contract = projects
    return run_native_acceptance(source_project=baseline, patched_project=patched,
                                 contract=contract, work_dir=tmp_path / 'runs')


def _resign(contract, *, packet=False):
    if packet:
        contract['packet']['packet_digest'] = evidence_packet_digest(contract['packet'])
    contract['contract_digest'] = content_digest({k: v for k, v in contract.items() if k != 'contract_digest'})


def test_tester_carries_native_node_and_full_fixture_binding(replay_case):
    _, spec = replay_case
    plan = build_test_plan(technical_spec=spec, implementation_plan={
        'implementation_target': {'candidate': TARGET}, 'patch_scope': [TARGET],
        'contract_binding': {'input_contract': {'exc': 'Any'}},
    })
    acceptance = plan['executable_acceptance']
    assert acceptance['format'] == 'native_failure_acceptance.v1'
    assert acceptance['status'] == 'ready'
    assert acceptance['obligations'][0]['nodeid'] == NODE
    assert acceptance['generated_samples'] is False
    assert 'sample' not in json.dumps(acceptance['obligations'])
    assert acceptance['packet']['project_inventory_digest']
    assert build_native_acceptance({'contract_mode': 'additive'}, TARGET) is None


def test_planning_reviewer_sees_ready_native_contract(replay_case):
    from runtime.review_findings_conformance import conformance_checks
    _, spec = replay_case
    plan = build_test_plan(technical_spec=spec, implementation_plan={
        'implementation_target': {'candidate': TARGET}, 'patch_scope': [TARGET]})
    checks = conformance_checks(spec, {}, plan, {}, {})
    assert next(row for row in checks if row['code'] == 'executable_acceptance_ready')['passed']
    incomplete = deepcopy(spec)
    incomplete['implementation_delta']['intent']['failure_evidence_packet'] = {}
    assert build_native_acceptance(incomplete, TARGET)['status'] != 'ready'
    incomplete = deepcopy(spec)
    incomplete['acceptance_criteria'] = []
    assert build_native_acceptance(incomplete, TARGET)['status'] != 'ready'


def test_real_stateful_fix_passes_without_claiming_full_regression(tmp_path, replay_case):
    projects = _copies(tmp_path, replay_case)
    before = [inventory(p) for p in projects[:2]]
    result = _run(tmp_path, projects)
    assert result['status'] == 'passed', result
    assert [row['returncode'] for row in result['probes']] == [1, 1, 0]
    summary = result['summary']
    assert summary['complete_native_regression'] == 'not_measured'
    assert summary['generated_test_count'] == 0
    assert result['source_inventory_digest'] != result['patched_inventory_digest']
    assert summary['acceptance_ids'] == ['AC-FAILURE-REPLAY-001']
    plan = {'implementation_target': {'candidate': TARGET}}
    assert acceptance_covers_plan(summary, plan)
    assert not acceptance_covers_plan(summary, {})
    assert not acceptance_covers_plan(summary, {**plan, 'change_plan': [{'target': 'other.py:call'}]})
    weakened = deepcopy(summary)
    weakened['native_replay_checks']['recorded_failure_reproduced'] = False
    assert not acceptance_covers_plan(weakened, plan)
    assert not acceptance_covers_plan({**summary, 'passed': False}, plan)
    assert not acceptance_covers_plan({**summary, 'replayed_test_count': 0}, plan)
    assert before == [inventory(p) for p in projects[:2]]


@pytest.mark.parametrize('change', ['noop', 'wrong_fix', 'test', 'fixture', 'config', 'stale_source',
                                  'packet_digest', 'contract_digest', 'missing_packet', 'nodeid', 'old_hash'])
def test_bad_patch_or_stale_handoff_cannot_pass(tmp_path, replay_case, change):
    baseline, patched, contract = projects = _copies(tmp_path, replay_case)
    if change == 'noop':
        (patched / 'channel.py').write_text(SOURCE)
    elif change == 'wrong_fix':
        (patched / 'channel.py').write_text(SOURCE.replace('pass', 'self.pending = []'))
    elif change == 'test':
        (patched / 'tests/test_channel.py').write_text(TEST.replace('assert pending == []', 'assert True'))
    elif change == 'fixture':
        (patched / 'tests/pending.json').write_text('[]')
    elif change == 'config':
        (patched / 'pytest.ini').write_text('[pytest]\naddopts = --deselect=' + NODE)
    elif change == 'stale_source':
        for project in (baseline, patched):
            (project / 'tests/pending.json').write_text('[3]')
    elif change == 'packet_digest':
        contract['packet']['failure_signature'] = 'forged'
        _resign(contract)
    elif change == 'contract_digest':
        contract['timeout_seconds'] = 1
    elif change == 'missing_packet':
        contract['packet'] = {}
        _resign(contract)
    elif change == 'nodeid':
        contract['obligations'][0]['nodeid'] = 'tests/test_channel.py::test_other'
        _resign(contract)
    elif change == 'old_hash':
        del contract['packet']['target_source']['file_sha256']
        _resign(contract, packet=True)
    result = _run(tmp_path, projects)
    assert result['status'] == 'failed', result
    assert not acceptance_covers_plan(result['summary'], {'implementation_target': {'candidate': TARGET}})


@pytest.mark.parametrize('behavior', ['skip', 'timeout', 'mutation', 'collection', 'fake_baseline'])
def test_execution_failures_remain_failures(tmp_path, replay_case, behavior):
    baseline, patched, contract = projects = _copies(tmp_path, replay_case)
    if behavior == 'fake_baseline':
        contract['packet']['failure_signature'] = 'invented-signature'
        _resign(contract, packet=True)
    else:
        insertion = {
            'skip': "__import__('pytest').skip('bypass')",
            'timeout': "__import__('time').sleep(10)",
            'mutation': "__import__('pathlib').Path('tests/pending.json').write_text('[]')",
            'collection': "raise SystemExit(0)",
        }[behavior]
        (patched / 'channel.py').write_text(FIXED + '\n' + insertion + '\n')
        if behavior == 'timeout':
            contract['timeout_seconds'] = 2
            _resign(contract)
    result = _run(tmp_path, projects)
    assert result['status'] == 'failed', result
    assert result['summary']['native_replay_targets'] == []


def test_malformed_contract_returns_structured_failure(tmp_path, replay_case):
    baseline, patched, _ = _copies(tmp_path, replay_case)
    result = _run(tmp_path, (baseline, patched, None))
    assert result['status'] == 'failed'


def test_executor_dispatch_preserves_native_acceptance(tmp_path, replay_case, monkeypatch):
    from runtime import programmer_verification
    baseline, patched, contract = _copies(tmp_path, replay_case)
    def forbidden(**kwargs):
        pytest.fail('native replay must not be replaced by generic callable discovery')
    monkeypatch.setattr(programmer_verification, 'run_executable_acceptance', forbidden)
    result = programmer_verification.run_test_result(
        root=tmp_path, project_dir=patched, source_project_dir=baseline,
        implementation_plan={'implementation_target': {'candidate': TARGET}},
        test_plan={'executable_acceptance': contract}, execution_dir=tmp_path / 'execution',
        run_verification=True, max_commands=0,
    )
    assert result['status'] == 'ok'
    assert result['executable_acceptance_result']['summary']['replayed_test_count'] == 1
