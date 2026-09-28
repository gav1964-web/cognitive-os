"""Source-bound diagnostic replay of native pytest tests with their fixtures."""
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path

from cognitive_replay.process import isolated_environment, run_command
from .native_failure_acceptance import _validate
from .repair_target_nomination import _packet_contract
from .repair_trial_binding import observed_packet, validate_repair_trial_source
from .project_native_failure_binding import _interpret_pytest_result
from .narrow_type_evidence_binding import content_digest
from .stage_finalization_workspace import inventory, snapshot

SCHEMA = 'native_repair_observations.v1'
STATE_SCHEMA = 'native_repair_observations.v2'
LIMITATIONS = ('Original selected pytest tests execute with fixtures in fresh trusted-code copies. '
    'Only explicitly named locals and bounded built-in values are recorded; opaque objects are not rendered. '
    'Assertions are never reevaluated. Reachability does not assert an individual pass. '
    'Whole test-call method observations are not proof of data flow or root cause. '
    'No patch, acceptance or execution authority is granted. No hostile-code attestation.')


def _hashes(state=False):
    return {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in
            ['native_repair_observation_probe.py', 'repair_observation_probe.py', 'repair_target_trace_probe.py'] +
            (['native_observation_values.py', 'repair_function_catalog.py'] if state else [])}


def _request(packet, method_fields, test_local_names, copy, control, state=None):
    nodeids = [*packet['failing_nodeids'], *((state or {}).get('preservation') or {}).get('nodeids', [])]
    config = next((copy / n for n in ['pytest.ini', '.pytest.ini', 'pyproject.toml', 'tox.ini', 'setup.cfg']
                   if (copy / n).is_file()), control / 'pytest.ini')
    arguments = [*nodeids, '-q', '--tb=long', '--assert=rewrite', '--color=no', '-p', 'no:cacheprovider',
        '-c', str(config), f'--rootdir={copy}', f'--basetemp={control / "tmp"}']
    return {'observed_target': observed_packet(packet)['target'], 'method_fields': method_fields,
        'test_local_names': list(test_local_names),
        'tests': [{'nodeid': n, 'path': n.partition('::')[0]} for n in nodeids], 'pytest_arguments': arguments,
        **({'source_files': state['source_files'], 'structured_values': True} if state else {})}


def _matches(observation, packet, fields, state=None):
    contrasts = ((state or {}).get('preservation') or {}).get('nodeids', [])
    nodes = [*packet['failing_nodeids'], *contrasts]
    rows = observation.get('rows', [])
    seen = {c['target'] for r in rows for c in r['calls']}
    covered = (bool(seen) and seen <= set(fields) and
               (packet['target'] not in fields or packet['target'] in seen)) if state else seen == set(fields)
    return (observation.get('selected') == nodes and [r['nodeid'] for r in rows] == nodes
        and all(r['test_outcome'] == ('passed' if r['nodeid'] in contrasts else 'failed')
                and not r.get('xfail', False) for r in rows)
        and covered)


def collect_native_repair_observations(project, packet, work_dir, *, method_fields, test_local_names=(),
                                       authorized=False, python_executable=None, source_files=None, preservation=None):
    if not authorized:
        raise ValueError('explicit_diagnostic_execution_authorization_required')
    project, work_dir = project.resolve(), work_dir.resolve()
    if work_dir.is_relative_to(project) or project.is_relative_to(work_dir):
        raise ValueError('diagnostic_output_must_be_external')
    before = inventory(project)
    _validate(_packet_contract(packet), before)
    validate_repair_trial_source(project, packet)
    if preservation is not None:
        from .repair_preservation import validate_preservation
        validate_preservation(packet, preservation, project)
        if source_files is None:
            raise ValueError('preservation_state_requires_explicit_source_files')
    state = {'source_files': list(source_files), 'preservation': deepcopy(preservation)} if source_files is not None else None
    # Reject unbounded/non-source fields before creating a copy or executing tests.
    from .native_repair_observation_probe import NativeTracker, selected_fields
    from .repair_assertion_contract import build_assertion_contract
    build_assertion_contract(packet)
    for test in packet['test_sources']:
        import textwrap
        selected_fields(textwrap.dedent(test['excerpt']), list(test_local_names))
    NativeTracker(project, _request(packet, method_fields, test_local_names, project, work_dir, state))
    python = Path(python_executable or sys.executable).resolve()
    work_dir.mkdir(parents=True, exist_ok=False)
    probe = Path(__file__).with_name('native_repair_observation_probe.py')
    result = {'schema_version': STATE_SCHEMA if state else SCHEMA, 'status': 'blocked', 'packet_digest': packet['packet_digest'],
        'project_inventory_digest': content_digest(before), 'probe_hashes': _hashes(bool(state)),
        'method_fields': deepcopy(method_fields), 'test_local_names': list(test_local_names),
        'python_executable': str(python), 'repeats': [], 'execution_authorized': False,
        'source_apply': False, 'limitations': LIMITATIONS}
    if state:
        result['state_scope'] = state
        result['limitations'] += (' AST shape/positions, source-verified functions and partial bindings are bounded '
            'structural projections, not a semantic interpretation. Yield is suspension, not function completion. '
            'Contrast tests retain their original assertions; selected fields are explicit, no arbitrary repr.')
    try:
        for repeat in range(2):
            control = work_dir / str(repeat)
            control.mkdir()
            copy = control / 'project'
            snapshot(project, copy, before)
            (control / 'pytest.ini').write_text('[pytest]\n', encoding='utf-8')
            request = _request(packet, method_fields, test_local_names, copy, control, state)
            path, output = control / 'request.json', control / 'observation.json'
            path.write_text(json.dumps(request), encoding='utf-8')
            run = run_command([str(python), '-I', str(probe), str(copy), str(path), str(output)],
                cwd=copy, timeout=60, env=isolated_environment(control / 'environment', python))
            text = run['stdout'] + '\n' + run['stderr']
            (control / 'output.txt').write_text(text, encoding='utf-8')
            observation = json.loads(output.read_text(encoding='utf-8')) if output.is_file() else {}
            parsed = _interpret_pytest_result(copy, run['returncode'], text, {})
            record = {'path': str(output), 'observation': observation, 'returncode': run['returncode'],
                'failure_signature': parsed.get('failure_signature'), 'copy_unchanged': inventory(copy) == before,
                'output_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest()}
            result['repeats'].append(record)
            if (run['returncode'] != 1 or parsed.get('failure_signature') != packet['failure_signature']
                    or not record['copy_unchanged'] or not _matches(observation, packet, method_fields, state)):
                raise ValueError('native_observation_did_not_reproduce_failure')
        if result['repeats'][0]['observation'] != result['repeats'][1]['observation']:
            raise ValueError('native_observations_not_repeatable')
        result['status'] = 'observed'
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result['reason'] = str(exc)[:240]
    result['source_unchanged'] = inventory(project) == before
    if not result['source_unchanged']:
        result.update(status='blocked', reason='original_source_changed')
    result['observations_digest'] = content_digest(result)
    (work_dir / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    if result['status'] != 'observed':
        raise ValueError('native_observations_blocked:' + result.get('reason', 'unknown'))
    validate_native_repair_observations(project, packet, result)
    return result


def validate_native_repair_observations(project, packet, evidence):
    before = inventory(project)
    _validate(_packet_contract(packet), before)
    validate_repair_trial_source(project, packet)
    state = evidence.get('state_scope')
    if state and state.get('preservation') is not None:
        from .repair_preservation import validate_preservation
        validate_preservation(packet, state['preservation'], project)
    if (evidence.get('schema_version') != (STATE_SCHEMA if state else SCHEMA) or evidence.get('status') != 'observed'
            or evidence.get('packet_digest') != packet['packet_digest']
            or evidence.get('project_inventory_digest') != content_digest(before)
            or evidence.get('probe_hashes') != _hashes(bool(state)) or evidence.get('source_unchanged') is not True
            or evidence.get('execution_authorized') is not False or evidence.get('source_apply') is not False
            or evidence.get('observations_digest') != content_digest({k: v for k, v in evidence.items() if k != 'observations_digest'})):
        raise ValueError('native_observations_stale_or_changed')
    repeats = evidence.get('repeats', [])
    if len(repeats) != 2 or repeats[0]['observation'] != repeats[1]['observation']:
        raise ValueError('native_observations_not_repeatable')
    for row in repeats:
        path = Path(row['path'])
        control, copy = path.parent, path.parent / 'project'
        text = (control / 'output.txt').read_text(encoding='utf-8')
        parsed = _interpret_pytest_result(copy, row['returncode'], text, {})
        observation = row['observation']
        if (path.name != 'observation.json' or row.get('copy_unchanged') is not True
                or row['returncode'] != 1 or row['failure_signature'] != packet['failure_signature']
                or parsed.get('failure_signature') != packet['failure_signature']
                or row['output_sha256'] != hashlib.sha256(text.encode('utf-8')).hexdigest()
                or json.loads(path.read_text(encoding='utf-8')) != observation or inventory(copy) != before
                or json.loads((control / 'request.json').read_text(encoding='utf-8')) != _request(
                    packet, evidence['method_fields'], evidence['test_local_names'], copy, control, state)
                or not _matches(observation, packet, evidence['method_fields'], state)):
            raise ValueError('native_observation_receipt_changed')


def native_observation_context(evidence, *, compact=False):
    rows = deepcopy(evidence['repeats'][0]['observation']['rows'])
    result = {'observations_digest': evidence['observations_digest'],
              'rows': rows, 'limitations': evidence['limitations']}
    if evidence.get('state_scope'):
        result['state_projection'] = 'bounded_python_state.v1'
        result['requested_targets'] = sorted(evidence['method_fields'])
        result['not_observed_targets_by_test'] = {r['nodeid']: sorted(set(evidence['method_fields']) -
            {c['target'] for c in r['calls']}) for r in rows}
    if compact:
        for row in rows:
            for call in row['calls']:
                previous = {}
                for event in call['events']:
                    current = event['locals']
                    event['locals'] = {k: v for k, v in current.items() if k not in previous or previous[k] != v}
                    previous = current
        result['locals_encoding'] = ('Per call, the first event contains all selected locals; later events contain '
            'only changed values. Omitted names retain their preceding value. Unbound is explicit. '
            'Every event, line, sequence and return is retained; full snapshots remain in the receipt.')
    return result
