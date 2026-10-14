"""Execute caller-declared native requirement tests on unchanged source copies."""
import json
import sys
import uuid
from pathlib import Path, PureWindowsPath

from .native_failure_acceptance import _probe
from .narrow_type_evidence_binding import content_digest
from .stage_finalization_workspace import inventory, snapshot, changed_files, owned_path
from .upstream_change_impact import symbol_interface


def requested_test_bindings(contract: dict, source: dict) -> list[dict]:
    rows = []
    if contract['constraints']:
        raise ValueError('arbitrary_constraints_require_semantic_review')
    for req in contract['requirements']:
        examples = req.get('acceptance_examples', [])
        if not examples:
            raise ValueError('each_requirement_needs_native_acceptance')
        if req['id'].startswith('REQ-FAILURE-'):
            raise ValueError('reserved_requirement_id')
        for example in examples:
            node = example.get('nodeid', '')
            name = node.partition('::')[0] if isinstance(node, str) else ''
            if (example.get('kind') != 'native_test' or example.get('expectation') != 'passes'
                    or example.get('baseline_expectation') not in {'passes', 'fails'}
                    or not name.endswith('.py') or name not in source or '::' not in node
                    or '\\' in node or '\n' in node or '\r' in node or len(node) > 1024
                    or node.startswith('-') or Path(name).is_absolute() or PureWindowsPath(name).drive
                    or '..' in Path(name).parts):
                raise ValueError('exact_existing_native_test_required')
            rows.append({'requirement_id': req['id'], 'nodeid': node, 'test_path': name,
                         'source_sha256': source[name], 'baseline_expectation': example['baseline_expectation']})
    if len(rows) > 32 or len({r['nodeid'] for r in rows}) > 16:
        raise ValueError('requested_acceptance_budget_exceeded')
    return rows


def verify_requested_acceptance(*, project: Path, patched: Path, contract: dict,
                                impact: dict, work_dir: Path, native_replay_settings=None) -> dict:
    from .native_replay_settings import replay_settings
    settings = replay_settings(native_replay_settings)
    project, patched, work_dir = project.resolve(), patched.resolve(), work_dir.resolve()
    if any(work_dir.is_relative_to(p) or p.is_relative_to(work_dir) for p in (project, patched)):
        raise ValueError('acceptance_output_must_be_outside_projects')
    original, proposed = inventory(project), inventory(patched)
    if (impact.get('impact_digest') != content_digest({k: v for k, v in impact.items() if k != 'impact_digest'})
            or any(original.get(name) != digest for name, digest in impact['scanned_sources'].items())):
        raise ValueError('change_impact_source_is_stale')
    bindings = requested_test_bindings(contract, original)
    if any(proposed.get(r['test_path']) != r['source_sha256'] for r in bindings):
        raise ValueError('requested_test_source_changed')
    interfaces = all(symbol_interface(patched, target) == fingerprint
                     for target, fingerprint in impact['interfaces'].items())
    work = work_dir / ('requirements-' + uuid.uuid4().hex[:10])
    baseline, candidate = work / 'baseline', work / 'candidate'
    snapshot(project, baseline, original)
    snapshot(patched, candidate, proposed)
    nodes = list(dict.fromkeys(r['nodeid'] for r in bindings))
    probes = [_probe(copy, work / name, nodes, settings['pytest_plugins'], settings['timeout_seconds'],
                     Path(sys.executable), collect_nodeids=True)
              for copy, name in ((baseline, 'baseline-check'), (candidate, 'candidate-check'))]
    unchanged = not any((changed_files(project, original), changed_files(patched, proposed),
                         changed_files(baseline, original), changed_files(candidate, proposed)))
    observed = {row['nodeid'] for row in bindings}
    # _probe exposes normalized collected IDs; require exact selection, not just a green subset.
    collected = probes[1]['selected_nodeids'] or []
    checks = {'interfaces_preserved': interfaces, 'sources_unchanged': unchanged,
        'baseline_expectations_met': all(test_outcome(probes[0], r['nodeid']) == r['baseline_expectation'] for r in bindings),
        'baseline_completed': probes[0]['returncode'] in (0, 1),
        'collection_preserved': probes[0]['collected'] == probes[1]['collected'],
        'requested_nodes_executed': set(collected) == observed and len(collected) == len(observed)
                                  and sorted(probes[0]['selected_nodeids'] or []) == sorted(collected),
        'requested_tests_passed': probes[1]['returncode'] == 0 and probes[1]['skipped'] == 0
                                   and probes[1]['passing'] == len(observed)}
    result = {'schema_version': 'upstream_requested_acceptance.v1',
        'status': 'passed' if all(checks.values()) else 'failed', 'checks': checks,
        'task_contract_digest': contract['contract_digest'], 'impact_digest': impact['impact_digest'],
        'source_inventory_digest': content_digest(original), 'patched_inventory_digest': content_digest(proposed),
        'bindings': bindings, 'probes': probes, 'native_replay_settings': settings,
        'semantic_test_adequacy': 'caller_asserted_not_independently_verified',
        'receipt_path': str(work / 'requirements.json')}
    result['receipt_digest'] = content_digest(result)
    Path(result['receipt_path']).write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


def test_outcome(probe: dict, nodeid: str) -> str:
    reports = [r for r in probe.get('test_reports') or [] if r['nodeid'] == nodeid]
    phases = {r['when']: r['outcome'] for r in reports}
    if len(reports) != 3 or phases.get('setup') != 'passed' or phases.get('teardown') != 'passed':
        return 'not_verified'
    return {'passed': 'passes', 'failed': 'fails'}.get(phases.get('call'), 'not_verified')
