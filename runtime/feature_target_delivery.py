"""Deploy exact reviewed bundles to a working tree with local runtime state.

Selected source dependencies are hash-bound. Explicit JSON fixture additions may
bridge stages; they cannot modify existing files or introduce executable code.
Unselected target files are neither copied into verification nor overwritten.
"""
import json
from pathlib import Path

from .feature_acceptance import probe, save
from .feature_delivery import reviewed_chain
from .feature_workspace import (copy_source, digest, install, inventory,
                                owned_path, permitted, verify_selected_source)


def compose_deliveries(deliveries, data_inputs):
    if not 1 <= len(deliveries) <= 8:
        raise ValueError('feature_target_delivery_count')
    original = current = baseline = None
    changes, used, targets, tests, environment, bindings = {}, set(), [], {}, {}, []
    evidence_roots = []
    for item in deliveries:
        path = Path(item).resolve()
        report = json.loads(path.read_text(encoding='utf-8'))
        project = Path(report['project'])
        evidence_roots.extend([project.resolve(), path.parent / 'project'])
        chain = reviewed_chain(project, [s['checkpoint'] for s in report['stages']])
        check = report['verification']
        if (report['status'] != 'verified' or report['source_apply']
                or report['source_hashes'] != chain['original']
                or report['final_hashes'] != chain['final']
                or inventory(path.parent / 'project') != chain['final']
                or check['returncode'] != 0 or not check['source_unchanged']
                or check['tests'] != chain['expected_tests']
                or not check['tests'] or any(v != 'passed' for v in check['tests'].values())):
            raise ValueError('feature_target_unverified_bundle')
        if original is None:
            baseline, original = project, chain['original']
            current = dict(original)
        additions = set(chain['original']) - set(current)
        if any(chain['original'].get(n) != h for n, h in current.items()):
            raise ValueError('feature_target_disconnected_chain')
        for name in sorted(additions):
            if (not permitted(name) or not name.startswith('tests/fixtures/')
                    or Path(name).suffix != '.json' or name in used
                    or data_inputs.get(name) != chain['original'][name]):
                raise ValueError('feature_target_unapproved_data_input')
            data = owned_path(project, name).read_bytes()
            json.loads(data)
            changes[name] = data
            used.add(name)
        current = chain['final']
        changes.update(chain['changes'])
        targets.extend(chain['targets'])
        tests.update(chain['expected_tests'])
        for name, value in chain['environment'].items():
            if name in environment and environment[name] != value:
                raise ValueError('feature_target_environment_conflict')
            environment[name] = value
        bindings.append({'path': str(path), 'sha256': digest(path.read_bytes())})
    if used != set(data_inputs):
        raise ValueError('feature_target_unused_data_input')
    return dict(baseline=baseline, original=original, final=current, changes=changes,
                targets=list(dict.fromkeys(targets)), tests=tests,
                environment=environment, bindings=bindings, evidence_roots=evidence_roots)


def deliver_to_target(*, target, deliveries, work, python, data_inputs=None, apply=False):
    target, work = Path(target).resolve(), Path(work).resolve()
    if work.exists() or work.is_relative_to(target) or target.is_relative_to(work):
        raise ValueError('feature_target_requires_external_workdir')
    inputs = dict(data_inputs or {})
    chain = compose_deliveries(deliveries, inputs)
    if any(p == e or p.is_relative_to(e) or e.is_relative_to(p)
           for p in (target, work) for e in chain['evidence_roots']):
        raise ValueError('feature_target_overlaps_evidence')
    verify_selected_source(target, chain['original'])
    for name in set(chain['changes']) - set(chain['original']):
        if owned_path(target, name).exists():
            raise ValueError('feature_target_new_file_collision')
    candidate = work / 'project'
    copy_source(chain['baseline'], candidate, chain['original'])
    for name, data in chain['changes'].items():
        path = owned_path(candidate, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    check = probe(candidate, work / 'checks', Path(python), chain['targets'], chain['environment'])
    passed = (check['returncode'] == 0 and check['source_unchanged']
              and check['tests'] == chain['tests'] and inventory(candidate) == chain['final'])
    result = dict(schema_version='feature_target_delivery.v1', status='verified' if passed else 'blocked',
                  target=str(target), source_apply=False, source_hashes=chain['original'],
                  final_hashes=chain['final'], bundles=chain['bindings'], data_inputs=inputs,
                  verification=check, source_scope='explicit reviewed dependencies; local state excluded')
    save(work / 'report.json', result)
    if passed and apply:
        if compose_deliveries(deliveries, inputs) != chain:
            raise ValueError('feature_target_bundle_changed_during_verification')
        result['installation'] = install(target, chain['original'], chain['changes'],
                                         work / 'backup', selected_source=True)
        verify_selected_source(target, chain['final'])
        result.update(status='installed', source_apply=True)
        save(work / 'report.json', result)
    return result
