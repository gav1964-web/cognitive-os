"""Existing passing tests become explicit preservation obligations, not new tests."""
import ast
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path, PureWindowsPath

from cognitive_replay.process import isolated_environment, run_command
from .narrow_type_evidence_binding import content_digest
from .stage_finalization_workspace import inventory, owned_path, snapshot


def _sources(project, nodeids):
    if not isinstance(nodeids, list) or not 1 <= len(nodeids) <= 8 or len(set(nodeids)) != len(nodeids):
        raise ValueError('one_to_eight_unique_preservation_tests_required')
    rows = []
    for nodeid in nodeids:
        path, sep, symbol = nodeid.partition('::')
        if (not sep or not symbol or len(nodeid) > 1024 or any(c in nodeid for c in '\r\n')
                or '\\' in path or PureWindowsPath(path).is_absolute() or path.startswith('-')):
            raise ValueError('invalid_preservation_nodeid')
        file = owned_path(project, path)
        if file.suffix != '.py' or file.stat().st_size > 1_000_000:
            raise ValueError('bounded_python_test_required')
        data = file.read_bytes()
        source = data.decode('utf-8')
        scope = ast.parse(source).body
        for part in symbol.split('[', 1)[0].split('::'):
            matches = [n for n in scope if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.name == part]
            if len(matches) != 1:
                raise ValueError('unique_preservation_test_function_required')
            node = matches[0]
            scope = node.body
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            raise ValueError('preservation_test_function_required')
        excerpt = ast.get_source_segment(source, node)
        if not excerpt or len(excerpt) > 4000:
            raise ValueError('preservation_source_budget')
        rows.append({'id': f'P{len(rows)+1:03d}', 'nodeid': nodeid, 'path': path,
            'file_sha256': hashlib.sha256(data).hexdigest(), 'source': excerpt,
            'source_sha256': hashlib.sha256(excerpt.encode('utf-8')).hexdigest()})
    return rows


def _probe(project, control, nodeids, python, timeout=60):
    control.mkdir(parents=True, exist_ok=False)
    config = next((project / n for n in ('pytest.ini', '.pytest.ini', 'pyproject.toml', 'tox.ini', 'setup.cfg')
                   if (project / n).is_file()), control / 'pytest.ini')
    if config.parent == control:
        config.write_text('[pytest]\n', encoding='utf-8')
    output = control / 'cases.json'
    args = [*nodeids, '-q', '--tb=long', '--assert=rewrite', '--color=no', '-p', 'no:cacheprovider',
            '-c', str(config), f'--rootdir={project}', f'--basetemp={control / "tmp"}']
    script = Path(__file__).with_name('repair_preservation_probe.py')
    run = run_command([str(python), '-I', str(script), str(project), str(output), json.dumps(args)],
                      cwd=project, timeout=timeout, env=isolated_environment(control / 'environment', python))
    (control / 'output.txt').write_text(run['stdout'] + '\n' + run['stderr'], encoding='utf-8')
    data = json.loads(output.read_text(encoding='utf-8')) if output.exists() else {}
    return {'returncode': run['returncode'], 'data': data, 'output_path': str(control / 'output.txt')}


def _passed(probe, nodeids):
    data = probe.get('data', {})
    rows, reports = data.get('cases', []), data.get('reports', [])
    return (probe.get('returncode') == 0 and probe.get('copy_unchanged') is True
        and [r.get('nodeid') for r in rows] == nodeids and all(r.get('supported') is True for r in rows)
        and len(reports) == 3 * len(nodeids)
        and all(r.get('outcome') == 'passed' and r.get('xfail') is False for r in reports)
        and all(sorted(r['when'] for r in reports if r['nodeid'] == n) == ['call', 'setup', 'teardown'] for n in nodeids))


def collect_preservation_evidence(*, project, packet, nodeids, work_dir, authorized=False, python_executable=None):
    if not authorized:
        raise ValueError('explicit_preservation_execution_authorization_required')
    from .native_failure_acceptance import _validate
    from .repair_target_nomination import _packet_contract
    from .repair_trial_binding import validate_repair_trial_source
    project, work_dir = Path(project).resolve(), Path(work_dir).resolve()
    if project.is_relative_to(work_dir) or work_dir.is_relative_to(project):
        raise ValueError('preservation_work_must_be_outside_project')
    before = inventory(project)
    _validate(_packet_contract(packet), before)
    validate_repair_trial_source(project, packet)
    sources = _sources(project, nodeids)
    if set(nodeids) & set(packet['failing_nodeids']) or any(r['path'] not in before for r in sources):
        raise ValueError('preservation_tests_must_be_owned_and_distinct_from_failure')
    python = (python_executable or Path(sys.executable)).resolve()
    work_dir.mkdir(parents=True, exist_ok=False)
    evidence = {'schema_version': 'repair_preservation.v1', 'status': 'blocked',
        'packet_digest': packet['packet_digest'], 'project_inventory_digest': content_digest(before),
        'nodeids': nodeids, 'test_sources': sources, 'probes': [],
        'probe_sha256': hashlib.sha256(Path(__file__).with_name('repair_preservation_probe.py').read_bytes()).hexdigest(),
        'execution_authorized': False, 'source_apply': False,
        'scope': 'Explicit selected existing tests; two passing baseline replays. Literal pytest parameters only. '
            'Not complete regression, test semantic adequacy, or hostile-code attestation. Fixture bodies may be absent.'}
    try:
        for i in range(2):
            copy = work_dir / f'baseline-{i}'
            snapshot(project, copy, before)
            probe = _probe(copy, work_dir / f'probe-{i}', nodeids, python)
            probe['copy_unchanged'] = inventory(copy) == before
            evidence['probes'].append(probe)
            if not _passed(probe, nodeids):
                raise ValueError('preservation_baseline_not_all_passed')
        if evidence['probes'][0]['data'] != evidence['probes'][1]['data']:
            raise ValueError('preservation_cases_not_repeatable')
        if inventory(project) != before:
            raise ValueError('preservation_original_changed')
        evidence['status'] = 'verified_baseline'
    except (ValueError, OSError, TypeError, KeyError) as exc:
        evidence['reason'] = str(exc)
    evidence['digest'] = content_digest(evidence)
    (work_dir / 'evidence.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    return evidence


def validate_preservation(packet, evidence, project=None):
    if (evidence.get('schema_version') != 'repair_preservation.v1' or evidence.get('status') != 'verified_baseline'
            or evidence.get('digest') != content_digest({k: v for k, v in evidence.items() if k != 'digest'})
            or evidence.get('packet_digest') != packet['packet_digest']
            or evidence.get('project_inventory_digest') != packet['project_inventory_digest']
            or evidence.get('execution_authorized') is not False or evidence.get('source_apply') is not False
            or evidence.get('probe_sha256') != hashlib.sha256(Path(__file__).with_name('repair_preservation_probe.py').read_bytes()).hexdigest()):
        raise ValueError('invalid_preservation_evidence')
    nodeids, probes, sources = evidence['nodeids'], evidence['probes'], evidence['test_sources']
    if (not 1 <= len(nodeids) <= 8 or len(set(nodeids)) != len(nodeids)
            or set(nodeids) & set(packet['failing_nodeids']) or len(probes) != 2
            or not all(_passed(p, nodeids) for p in probes) or probes[0]['data'] != probes[1]['data']
            or [s['nodeid'] for s in sources] != nodeids
            or [s['id'] for s in sources] != [f'P{i+1:03d}' for i in range(len(nodeids))]
            or any(hashlib.sha256(s['source'].encode('utf-8')).hexdigest() != s['source_sha256'] for s in sources)):
        raise ValueError('invalid_preservation_baseline')
    if project is not None and (content_digest(inventory(project)) != evidence['project_inventory_digest']
                                or _sources(project, nodeids) != sources):
        raise ValueError('stale_preservation_source')
    if project is not None:
        for probe in probes:
            output = Path(probe['output_path']).resolve()
            receipt = output.with_name('cases.json')
            if (output.name != 'output.txt' or receipt.is_relative_to(Path(project).resolve())
                    or receipt.stat().st_size > 200000
                    or json.loads(receipt.read_text(encoding='utf-8')) != probe['data']):
                raise ValueError('preservation_probe_receipt_changed')


def preservation_context(evidence):
    return {'digest': evidence['digest'], 'scope': evidence['scope'], 'cases': [
        {'id': s['id'], 'nodeid': s['nodeid'], 'source': s['source'], 'parameters': r['parameters']}
        for s, r in zip(evidence['test_sources'], evidence['probes'][0]['data']['cases'])]}


def validate_preservation_plan(evidence, plan):
    expected = [s['id'] for s in evidence.get('test_sources', evidence.get('cases', []))]
    if (not isinstance(plan, list) or len(plan) != len(expected)
            or any(not isinstance(r, dict) or set(r) != {'case_id', 'behavior'}
                   or not isinstance(r['behavior'], str) or not 12 <= len(r['behavior'].strip()) <= 800 for r in plan)
            or [r['case_id'] for r in plan] != expected):
        raise ValueError('complete_preservation_plan_required')


def bind_preservation(diagnosis, project, evidence):
    result = deepcopy(diagnosis)
    issues = [i for i in result.get('issues', []) if i.get('failure_specific_reducer_required')]
    if len(issues) != 1:
        raise ValueError('single_preservation_issue_required')
    validate_preservation(issues[0]['failure_evidence_packet'], evidence, project)
    issues[0]['preservation_evidence'] = deepcopy(evidence)
    return result


def check_candidate_preservation(project, candidate, packet, evidence, work_dir):
    validate_preservation(packet, evidence, project)
    before = inventory(candidate)
    copy = work_dir / 'project'
    snapshot(candidate, copy, before)
    probe = _probe(copy, work_dir / 'probe', evidence['nodeids'], Path(sys.executable))
    probe['copy_unchanged'] = inventory(copy) == before and inventory(candidate) == before
    same_cases = probe['data'].get('cases') == evidence['probes'][0]['data']['cases']
    return {'status': 'passed' if same_cases and _passed(probe, evidence['nodeids']) else 'failed',
            'preservation_digest': evidence['digest'], 'same_cases': same_cases, 'probe': probe}
