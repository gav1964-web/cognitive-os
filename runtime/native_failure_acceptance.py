"""Paired replay of a source-bound failing test, preserving its stateful fixture.

This is targeted behavioral acceptance. Complete native regression and final
review remain separate gates. Execution uses copies of trusted project code.
"""
from __future__ import annotations

import json
import re
import sys
import uuid
import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path, PureWindowsPath

from cognitive_replay.process import isolated_environment, run_command
from .failure_input_reduction import failure_signature
from .narrow_type_evidence_binding import content_digest
from .project_failure_evidence_packet import is_complete_failure_evidence_packet
from .project_native_failure_binding import _interpret_pytest_result, _stable_summary
from .stage_finalization_workspace import inventory, snapshot, changed_files

FORMAT = 'native_failure_acceptance.v1'
REQUIRED_CHECKS = (
    'source_packet_current', 'patch_scope_preserved', 'baseline_failure_repeated',
    'recorded_failure_reproduced', 'patched_tests_passed', 'test_collection_preserved',
    'source_copies_unchanged', 'input_projects_unchanged',
)


def build_native_acceptance(spec: dict, target: str) -> dict | None:
    if spec.get('contract_mode') != 'failure_repair':
        return None
    packet = deepcopy(spec.get('implementation_delta', {}).get('intent', {}).get('failure_evidence_packet') or {})
    from .native_replay_settings import replay_settings
    settings = replay_settings(packet.get('observation_packet', packet).get('native_replay_settings'))
    contract = {
        'format': FORMAT, 'target': target, 'packet': packet,
        'scope': 'targeted_failure_replay; complete_native_regression_required_separately',
        'obligations': [
            {'id': row['id'], 'acceptance_id': row['id'], 'target': target,
             'kind': 'project_native_failure_replay', 'nodeid': nodeid}
            for row, nodeid in zip(
                [r for r in spec.get('acceptance_criteria', []) if r.get('id', '').startswith('AC-FAILURE-REPLAY-')],
                packet.get('failing_nodeids', []),
            )
        ],
        'timeout_seconds': settings['timeout_seconds'],
        'pytest_plugins': settings['pytest_plugins'],
        'generated_samples': False,
    }
    ready = (is_complete_failure_evidence_packet(packet, target=target)
             and bool(packet.get('project_inventory_digest')) and bool(contract['obligations'])
             and len(contract['obligations']) == len(packet.get('failing_nodeids', []))
             and all(row.get('file_sha256') for row in
                     [packet.get('target_source') or {}, *packet.get('test_sources', [])]))
    contract['status'] = 'ready' if ready else 'blocked_incomplete_native_contract'
    contract['contract_digest'] = content_digest(contract)
    return contract


def native_coverage(summary: dict, targets: set[str]) -> bool:
    checks = summary.get('native_replay_checks') or {}
    return (summary.get('signal_strength') == 'native_failure_replay'
            and summary.get('passed') is True and type(summary.get('replayed_test_count')) is int
            and summary['replayed_test_count'] > 0
            and bool(targets) and set(summary.get('native_replay_targets') or []) == targets
            and all(checks.get(key) is True for key in REQUIRED_CHECKS))


def preflight_native_acceptance(*, source_project: Path, contract: dict,
                                work_dir: Path, python_executable: Path | None = None) -> dict:
    """Repeat the recorded baseline with the acceptance runner before model IO.

    This checks protocol/environment compatibility, not patch acceptance. The
    paired candidate replay must still repeat its own baseline and full gates.
    """
    control = work_dir / ('native_preflight-' + uuid.uuid4().hex[:10])
    control.mkdir(parents=True)
    probes, original, reason = [], {}, None
    checks = dict.fromkeys(('source_packet_current', 'baseline_failure_repeated',
        'recorded_failure_reproduced', 'source_copies_unchanged', 'input_project_unchanged'), False)
    try:
        source_project = source_project.resolve()
        original = inventory(source_project)
        _, nodeids, plugins, timeout = _validate(contract, original)
        from .repair_trial_binding import validate_repair_trial_source
        validate_repair_trial_source(source_project, contract['packet'])
        checks['source_packet_current'] = True
        baseline = control / 'baseline'
        snapshot(source_project, baseline, original)
        for index in range(2):
            probes.append(_probe(baseline, control / f'baseline-{index}', nodeids,
                plugins, timeout, python_executable or Path(sys.executable)))
            if changed_files(baseline, original):
                raise ValueError('baseline_test_mutated_source')
        signatures = [_replay_signature(row) for row in probes]
        checks['baseline_failure_repeated'] = bool(signatures[0]) and signatures[0] == signatures[1]
        checks['recorded_failure_reproduced'] = all(
            row['intake_signature'] == contract['packet']['failure_signature'] for row in probes)
        checks['source_copies_unchanged'] = not changed_files(baseline, original)
        checks['input_project_unchanged'] = not changed_files(source_project, original)
        if not checks['baseline_failure_repeated'] or not checks['recorded_failure_reproduced']:
            raise ValueError('recorded_baseline_not_reproduced')
    except (OSError, ValueError, TypeError, KeyError, AttributeError, ET.ParseError) as exc:
        reason = str(exc)
    passed = all(checks.values())
    result = {'schema_version': 'native_model_preflight.v1', 'status': 'passed' if passed else 'blocked',
        'reason': reason or (None if passed else 'source_changed_during_preflight'),
        'checks': checks, 'probes': probes, 'source_inventory_digest': content_digest(original),
        'contract_digest': contract.get('contract_digest') if isinstance(contract, dict) else None,
        'next_action': None if passed else 'repeat_intake_with_acceptance_assertion_mode_and_environment',
        'assertion_mode': 'rewrite', 'model_calls': 0, 'source_apply': False,
        'patch_acceptance_authority': False, 'result_path': str(control / 'result.json')}
    Path(result['result_path']).write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


def run_native_acceptance(*, source_project: Path, patched_project: Path,
                          contract: dict, work_dir: Path, python_executable: Path | None = None) -> dict:
    control = work_dir / ('native_acceptance-' + uuid.uuid4().hex[:10])
    control.mkdir(parents=True)
    checks = dict.fromkeys(REQUIRED_CHECKS, False)
    probes, error = [], None
    original, patched = {}, {}
    try:
        source_project, patched_project = source_project.resolve(), patched_project.resolve()
        original, patched = inventory(source_project), inventory(patched_project)
        target, nodeids, plugins, timeout = _validate(contract, original)
        from .repair_trial_binding import validate_repair_trial_source, validate_repair_patch_scope
        validate_repair_trial_source(source_project, contract['packet'])
        checks['source_packet_current'] = True
        delta = {name for name in original.keys() | patched.keys() if original.get(name) != patched.get(name)}
        path = target.partition(':')[0]
        if delta != {path} or path not in patched:
            raise ValueError('patch_must_change_only_the_bound_production_file')
        validate_repair_patch_scope((source_project / path).read_bytes().decode('utf-8'),
            (patched_project / path).read_bytes().decode('utf-8'), contract['packet'])
        checks['patch_scope_preserved'] = True
        baseline_copy, patched_copy = control / 'baseline', control / 'patched'
        snapshot(source_project, baseline_copy, original)
        snapshot(patched_project, patched_copy, patched)
        python = python_executable or Path(sys.executable)
        for index in range(2):
            probes.append(_probe(baseline_copy, control / f'baseline-{index}', nodeids, plugins, timeout, python))
            if changed_files(baseline_copy, original):
                raise ValueError('baseline_test_mutated_source')
        signatures = [_replay_signature(row) for row in probes]
        checks['baseline_failure_repeated'] = bool(signatures[0]) and signatures[0] == signatures[1]
        checks['recorded_failure_reproduced'] = all(
            row['intake_signature'] == contract['packet']['failure_signature'] for row in probes)
        if not checks['baseline_failure_repeated'] or not checks['recorded_failure_reproduced']:
            raise ValueError('recorded_baseline_not_reproduced')
        result = _probe(patched_copy, control / 'patched-check', nodeids, plugins, timeout, python)
        probes.append(result)
        checks['patched_tests_passed'] = result['returncode'] == 0 and result['passing'] > 0 and result['skipped'] == 0
        checks['test_collection_preserved'] = probes[0]['collected'] == probes[1]['collected'] == result['collected']
        checks['source_copies_unchanged'] = not changed_files(baseline_copy, original) and not changed_files(patched_copy, patched)
        checks['input_projects_unchanged'] = not changed_files(source_project, original) and not changed_files(patched_project, patched)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, ET.ParseError) as exc:
        error = f'{type(exc).__name__}:{exc}'
    contract = contract if isinstance(contract, dict) else {}
    passed = all(checks.values())
    result = {
        'artifact_type': 'ExecutableAcceptanceResult', 'status': 'passed' if passed else 'failed',
        'format': FORMAT, 'scope': 'targeted_failure_replay_only',
        'reason': error or (None if passed else 'failed_checks:' + ','.join(k for k, v in checks.items() if not v)),
        'source_inventory_digest': content_digest(original) if original else None,
        'patched_inventory_digest': content_digest(patched) if patched else None,
        'trust_boundary': 'trusted-code subprocess copies; not an OS sandbox',
        'contract_digest': contract.get('contract_digest'), 'probes': probes,
        'summary': {
            'signal_strength': 'native_failure_replay', 'native_replay_checks': checks,
            'native_replay_targets': [contract.get('target')] if passed else [],
            'acceptance_ids': [r['acceptance_id'] for r in contract.get('obligations', [])] if passed else [],
            'callable_harness_count': 0, 'generated_test_count': 0,
            'replayed_test_count': probes[-1]['passing'] if passed else 0,
            'complete_native_regression': 'not_measured', 'passed': passed,
        },
        'source_code_changes': False, 'registry_changes': False,
        'result_path': str(control / 'result.json'),
    }
    Path(result['result_path']).write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


def _replay_signature(probe):
    signature = failure_signature(probe)
    if signature:
        for row in signature:
            if row[-1] is not None:
                row[-1] = _stable_summary(row[-1])
    return signature


def _validate(contract, source):
    body = {k: v for k, v in contract.items() if k != 'contract_digest'}
    if contract.get('format') != FORMAT or content_digest(body) != contract.get('contract_digest'):
        raise ValueError('invalid_native_acceptance_contract')
    target, packet = contract.get('target', ''), contract.get('packet') or {}
    if not is_complete_failure_evidence_packet(packet, target=target):
        raise ValueError('complete_failure_packet_required')
    if packet.get('project_inventory_digest') != content_digest(source):
        raise ValueError('stale_project_inventory')
    for item in [packet['target_source'], *packet['test_sources']]:
        if not item.get('file_sha256') or source.get(item['path']) != item['file_sha256']:
            raise ValueError('stale_bound_source_file')
    path = target.partition(':')[0]
    if not path.endswith('.py') or any(p.startswith('test') for p in Path(path).parts):
        raise ValueError('production_target_required')
    rows = contract.get('obligations') or []
    nodeids = [row['nodeid'] for row in rows]
    if (not 1 <= len(nodeids) <= 8 or len(set(nodeids)) != len(nodeids)
            or nodeids != packet['failing_nodeids'] or len({r['acceptance_id'] for r in rows}) != len(rows)
            or any(r.get('target') != target or r.get('kind') != 'project_native_failure_replay' for r in rows)):
        raise ValueError('native_test_binding_mismatch')
    for nodeid in nodeids:
        name = nodeid.partition('::')[0]
        if (not name.endswith('.py') or name not in source or '\\' in name or any(c in nodeid for c in '\r\n')
                or nodeid.startswith('-') or Path(name).is_absolute() or PureWindowsPath(name).is_absolute()
                or '..' in Path(name).parts):
            raise ValueError('invalid_native_test_path')
    plugins, timeout = contract.get('pytest_plugins', []), contract.get('timeout_seconds')
    if type(timeout) is not int or not 1 <= timeout <= 120:
        raise ValueError('invalid_native_replay_timeout')
    if not isinstance(plugins, list) or len(plugins) > 4 or any(not re.fullmatch(r'[A-Za-z_]\w*(?:\.\w+)*', p) for p in plugins):
        raise ValueError('invalid_pytest_plugins')
    return target, nodeids, plugins, timeout


def _probe(project, control, nodeids, plugins, timeout, python, *, collect_nodeids=False, pytest_arguments=None):
    control.mkdir()
    junit = control / 'pytest.xml'
    bootstrap = ('import sys,json;from pathlib import Path;p=Path(sys.argv[1]);'
                 'sys.path[:0]=[str(p),str(p/"src")];import pytest;'
                 'raise SystemExit(pytest.main(json.loads(sys.argv[2])))')
    if collect_nodeids:
        bootstrap = ('import sys,json;from pathlib import Path;p=Path(sys.argv[1]);'
            'sys.path[:0]=[str(p),str(p/"src")];import pytest;selected=[];reports=[];selection_output=Path(sys.argv[3]);'
            'tracker=type("Selection",(),{"pytest_collection_finish":lambda self,session:'
            'selected.extend(item.nodeid for item in session.items),'
            '"pytest_runtest_logreport":lambda self,report:reports.append({"nodeid":report.nodeid,"when":report.when,"outcome":report.outcome,'
            '"failure_message":str(getattr(getattr(report.longrepr,"reprcrash",None),"message",""))[:1000]})})();'
            'code=pytest.main(json.loads(sys.argv[2]),plugins=[tracker]);'
            'selection_output.write_text(json.dumps({"selected":selected,"reports":reports}),encoding="utf-8");raise SystemExit(code)')
    config = next((project / n for n in ('pytest.ini', '.pytest.ini', 'pyproject.toml', 'tox.ini', 'setup.cfg')
                   if (project / n).is_file()), control / 'pytest.ini')
    if config.parent == control:
        config.write_text('[pytest]\n')
    arguments = [*(pytest_arguments or []), *nodeids, '-q', '--tb=long', '--assert=rewrite', '--color=no',
                 '-p', 'no:cacheprovider', '-c', str(config),
                 f'--rootdir={project}', f'--basetemp={control / "tmp"}', f'--junitxml={junit}']
    for plugin in plugins:
        arguments.extend(['-p', plugin])
    selection_path = control / 'selected-nodeids.json'
    command = [str(python), '-I', '-c', bootstrap, str(project), json.dumps(arguments)]
    if collect_nodeids:
        command.append(str(selection_path))
    run = run_command(command,
                      cwd=project, timeout=timeout, env=isolated_environment(control / 'environment', python))
    output = run['stdout'] + '\n' + run['stderr']
    (control / 'output.txt').write_text(output, encoding='utf-8')
    parsed = _interpret_pytest_result(project, run['returncode'], output, {})
    collected, passing, skipped = [], 0, 0
    if junit.is_file():
        for case in ET.parse(junit).iter('testcase'):
            collected.append([case.get('classname'), case.get('name')])
            passing += not any(case.find(tag) is not None for tag in ('failure', 'error', 'skipped'))
            skipped += case.find('skipped') is not None
    selection = json.loads(selection_path.read_text(encoding='utf-8')) if selection_path.exists() else {}
    return {'returncode': run['returncode'], 'junit': str(junit), 'passing': passing,
            'selected_nodeids': selection.get('selected'), 'test_reports': selection.get('reports'),
            'skipped': skipped, 'collected': sorted(collected),
            'intake_signature': parsed.get('failure_signature'), 'output': str(control / 'output.txt')}
