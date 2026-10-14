"""Compose exact reviewed COS checkpoints and recheck before opt-in installation.

No model calls or domain logic. Historical receipts are local evidence, not a
security signature. Every stage must preserve the previous complete inventory.
"""
import json
from pathlib import Path

from .feature_acceptance import probe, save, validate_spec
from .feature_checkpoint import load_roles, qualified_spec, verified_candidate
from .feature_corpus_checks import input_inventory
from .feature_workspace import (copy_source, digest, install, inventory,
                                materialize_edits, owned_path)


def reviewed_chain(project, checkpoints):
    if not 1 <= len(checkpoints) <= 8:
        raise ValueError('feature_delivery_checkpoint_count')
    original = current = inventory(project)
    changes, stages, expected_tests, environments, targets = {}, [], {}, {}, []
    for name in checkpoints:
        path = Path(name).resolve()
        report = json.loads((path / 'report.json').read_text(encoding='utf-8'))
        source = json.loads((path / 'source-inventory.json').read_text(encoding='utf-8'))
        review = json.loads((path / 'reviewer.json').read_text(encoding='utf-8'))
        if (report['status'] != 'verified' or source != current
                or review != report['artifacts'].get('reviewer')
                or review.get('status') != 'ready' or review.get('decision') != 'approve'):
            raise ValueError('feature_delivery_unreviewed_or_disconnected_chain')
        baseline = Path(report['project']).resolve()
        if inventory(baseline) != source:
            raise ValueError('feature_delivery_checkpoint_source_changed')
        roles, _ = load_roles(path, baseline, source, report['goal'])
        spec = qualified_spec(path)['accepted']
        tests = validate_spec(spec, source)
        candidate = verified_candidate(path)
        edits = materialize_edits(baseline, source, candidate['proposal']['edits'],
                                  roles['architect']['scope'], frozen_tests=tests)
        patch = {**tests, **edits}
        hashes = {n: digest(b) for n, b in patch.items()}
        if hashes != candidate['candidate_hashes']:
            raise ValueError('feature_delivery_candidate_changed')
        changes.update(patch)
        current = {**current, **hashes}
        targets.extend([*tests, *spec['regression_tests']])
        environments.update(spec.get('environment', {}))
        expected_tests.update(report['attempts'][-1]['tests'])
        stages.append({'checkpoint': str(path), 'report_sha256': digest((path / 'report.json').read_bytes()),
                       'candidate_hashes': hashes, 'limitations': review.get('limitations', []),
                       'goal_complete': review.get('goal_complete') is True})
    return {'original': original, 'final': current, 'changes': changes, 'stages': stages,
            'targets': list(dict.fromkeys(targets)), 'environment': environments,
            'expected_tests': expected_tests}


def deliver_feature(*, project, checkpoints, work, python, apply_source=False,
                    corpus_receipt=None):
    project, work = Path(project).resolve(), Path(work).resolve()
    if work.exists() or work.is_relative_to(project) or project.is_relative_to(work):
        raise ValueError('feature_delivery_requires_fresh_external_workdir')
    chain = reviewed_chain(project, checkpoints)
    corpus = None
    if corpus_receipt:
        receipt = Path(corpus_receipt).resolve()
        corpus = json.loads(receipt.read_text(encoding='utf-8'))
        if (corpus.get('schema_version') != 'feature_corpus_checks.v1'
                or corpus.get('status') != 'passed' or corpus.get('regressions')
                or set(corpus.get('checks', {})) != {'baseline', 'candidate'}
                or {**corpus['source_hashes'], **corpus['candidate_hashes']} != chain['final']
                or not corpus.get('source_unchanged') or not corpus.get('original_inputs_unchanged')
                or any(c['returncode'] != 0 or not c['source_unchanged'] or not c['inputs_unchanged']
                       or not c['counts']['passed'] or c['counts']['skipped']
                       or not c['tests'] or any(v != 'passed' for v in c['tests'].values())
                       for c in corpus['checks'].values())
                or input_inventory(project, list(corpus['input_hashes']), chain['original']) != corpus['input_hashes']):
            raise ValueError('feature_delivery_corpus_not_bound')
    work.mkdir(parents=True)
    candidate = work / 'project'
    copy_source(project, candidate, chain['original'])
    for name, body in chain['changes'].items():
        file = owned_path(candidate, name)
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(body)
    check = probe(candidate, work / 'checks', Path(python), chain['targets'], chain['environment'])
    passed = (check['returncode'] == 0 and check['source_unchanged']
              and check['tests'] and set(check['tests']) == set(chain['expected_tests'])
              and all(v == 'passed' for v in check['tests'].values())
              and inventory(candidate) == chain['final']
              and inventory(project) == chain['original'])
    result = {'schema_version': 'feature_delivery.v1', 'status': 'verified' if passed else 'blocked',
              'project': str(project), 'source_apply': False, 'stages': chain['stages'],
              'source_hashes': chain['original'], 'final_hashes': chain['final'], 'verification': check,
              'limitations': list(dict.fromkeys(x for s in chain['stages'] for x in s['limitations']))}
    if corpus:
        result['corpus_receipt'] = {'path': str(receipt), 'sha256': digest(receipt.read_bytes())}
    save(work / 'report.json', result)
    if passed and apply_source:
        # Recheck all bindings after execution, before entering the transaction.
        fresh = reviewed_chain(project, checkpoints)
        if fresh != chain:
            raise ValueError('feature_delivery_chain_changed_during_verification')
        if corpus and (digest(receipt.read_bytes()) != result['corpus_receipt']['sha256']
                or input_inventory(project, list(corpus['input_hashes']), chain['original']) != corpus['input_hashes']):
            raise ValueError('feature_delivery_corpus_changed_during_verification')
        result['installation'] = install(project, chain['original'], chain['changes'], work / 'backup')
        result.update(status='installed', source_apply=True,
                      installed_inventory_matches=inventory(project) == chain['final'])
        save(work / 'report.json', result)
    return result
