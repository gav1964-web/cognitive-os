"""Repeatable per-assertion diagnostics in fresh copies, separate from native tests."""
import hashlib
import json
import sys
import textwrap
from pathlib import Path

from cognitive_replay.process import isolated_environment, run_command
from .native_failure_acceptance import _validate
from .repair_target_nomination import _packet_contract
from .repair_trial_binding import validate_repair_trial_source
from .repair_assertion_contract import build_assertion_contract
from .narrow_type_evidence_binding import content_digest
from .stage_finalization_workspace import inventory, snapshot

LIMITATIONS = ('Source-derived isolated equality probes, each in a fresh process/copy; fixture/setup/sequence '
    'semantics are not replayed. Outcomes are diagnostic only, not original native-suite outcomes or execution authority. '
    'Argument values are captured only for explicitly named fields using bounded built-in serialization. Trusted code only.')


def collect_repair_observations(project, packet, work_dir, *, argument_names=(), authorized=False, python_executable=None):
    if not authorized:
        raise ValueError('explicit_diagnostic_execution_authorization_required')
    project, work_dir = project.resolve(), work_dir.resolve()
    if work_dir.is_relative_to(project) or project.is_relative_to(work_dir):
        raise ValueError('diagnostic_output_must_be_external')
    before = inventory(project)
    _validate(_packet_contract(packet), before)
    validate_repair_trial_source(project, packet)
    contract = build_assertion_contract(packet)
    if len(contract['assertions']) > 8:
        raise ValueError('diagnostic_assertion_budget_exceeded')
    probe = Path(__file__).with_name('repair_observation_probe.py')
    python = Path(python_executable or sys.executable).resolve()
    work_dir.mkdir(parents=True, exist_ok=False)
    rows = []
    for assertion in contract['assertions']:
        if len(assertion['nodeids']) != 1:
            raise ValueError('unparameterized_diagnostic_test_required')
        test = next(r for r in packet['test_sources'] if r['nodeid'] == assertion['nodeids'][0])
        repeats = []
        for repeat in range(2):
            control = work_dir / f'{assertion["id"]}-{repeat}'
            control.mkdir()
            copy = control / 'project'
            snapshot(project, copy, before)
            config = control / 'pytest.ini'
            config.write_text('[pytest]\n', encoding='utf-8')
            request = {**assertion, 'nodeid': assertion['nodeids'][0], 'test_path': assertion['path'],
                'excerpt': textwrap.dedent(test['excerpt']), 'target': packet['target'], 'argument_names': list(argument_names),
                'pytest_arguments': [assertion['nodeids'][0], '--collect-only', '-q', '-p', 'no:cacheprovider',
                    '-c', str(config), f'--confcutdir={copy}', f'--rootdir={copy}', f'--basetemp={control / "tmp"}']}
            request_path, output = control / 'request.json', control / 'observation.json'
            request_path.write_text(json.dumps(request), encoding='utf-8')
            run = run_command([str(python), '-I', str(probe), str(copy), str(request_path), str(output)],
                cwd=copy, timeout=30, env=isolated_environment(control / 'env', python))
            (control / 'output.txt').write_text(run['stdout'] + run['stderr'], encoding='utf-8')
            if run['returncode'] != 0 or not output.is_file() or inventory(copy) != before:
                raise ValueError('isolated_observation_failed:' + str(control))
            repeats.append({'path': str(output), 'observation': json.loads(output.read_text()), 'copy_unchanged': True})
        if repeats[0]['observation'] != repeats[1]['observation']:
            raise ValueError('isolated_observation_not_repeatable')
        rows.append({'id': assertion['id'], 'repeats': repeats})
    result = {'schema_version': 'repair_observations.v1', 'packet_digest': packet['packet_digest'],
        'contract_digest': contract['contract_digest'], 'project_inventory_digest': content_digest(before),
        'probe_sha256': hashlib.sha256(probe.read_bytes()).hexdigest(),
        'base_probe_sha256': hashlib.sha256(probe.with_name('repair_target_trace_probe.py').read_bytes()).hexdigest(),
        'argument_names': list(argument_names), 'observations': rows, 'python_executable': str(python),
        'source_unchanged': inventory(project) == before, 'execution_authorized': False, 'limitations': LIMITATIONS}
    result['observations_digest'] = content_digest(result)
    (work_dir / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    validate_repair_observations(project, packet, result)
    return result


def validate_repair_observations(project, packet, evidence):
    if evidence.get('schema_version') in {'native_repair_observations.v1', 'native_repair_observations.v2'}:
        from .native_repair_observations import validate_native_repair_observations
        return validate_native_repair_observations(project, packet, evidence)
    before = inventory(project)
    _validate(_packet_contract(packet), before)
    validate_repair_trial_source(project, packet)
    contract = build_assertion_contract(packet)
    probe = Path(__file__).with_name('repair_observation_probe.py')
    if (evidence.get('schema_version') != 'repair_observations.v1'
            or evidence.get('observations_digest') != content_digest({k:v for k,v in evidence.items() if k!='observations_digest'})
            or evidence.get('packet_digest') != packet['packet_digest']
            or evidence.get('contract_digest') != contract['contract_digest']
            or evidence.get('project_inventory_digest') != content_digest(before)
            or evidence.get('probe_sha256') != hashlib.sha256(probe.read_bytes()).hexdigest()
            or evidence.get('base_probe_sha256') != hashlib.sha256(probe.with_name('repair_target_trace_probe.py').read_bytes()).hexdigest()
            or evidence.get('source_unchanged') is not True or evidence.get('execution_authorized') is not False
            or [r['id'] for r in evidence['observations']] != [r['id'] for r in contract['assertions']]):
        raise ValueError('repair_observations_stale_or_changed')
    for row in evidence['observations']:
        repeats = row['repeats']
        if len(repeats) != 2 or repeats[0]['observation'] != repeats[1]['observation']:
            raise ValueError('repeatable_observations_required')
        for repetition in repeats:
            path = Path(repetition['path'])
            request = json.loads(path.with_name('request.json').read_text())
            assertion = next(a for a in contract['assertions'] if a['id'] == row['id'])
            excerpt = next(r['excerpt'] for r in packet['test_sources'] if r['nodeid'] == request['nodeid'])
            if (request['argument_names'] != evidence['argument_names'] or request['target'] != packet['target']
                    or request['id'] != row['id'] or request['assertion'] != assertion['assertion']
                    or request['excerpt'] != textwrap.dedent(excerpt)
                    or inventory(path.parent / 'project') != before):
                raise ValueError('observation_request_or_copy_changed')
            if (repetition.get('copy_unchanged') is not True or repetition['observation'].get('id') != row['id']
                    or json.loads(path.read_text()) != repetition['observation']):
                raise ValueError('observation_receipt_changed')


def observation_context(evidence, *, compact=False):
    if evidence.get('schema_version') in {'native_repair_observations.v1', 'native_repair_observations.v2'}:
        from .native_repair_observations import native_observation_context
        return native_observation_context(evidence, compact=compact)
    rows = []
    for item in evidence['observations']:
        row = item['repeats'][0]['observation']
        calls = {content_digest(c): c for c in row['calls']}
        rows.append({**{k:v for k,v in row.items() if k!='calls'}, 'distinct_calls': list(calls.values())})
    return {'observations_digest': evidence['observations_digest'], 'rows': rows, 'limitations': LIMITATIONS}
