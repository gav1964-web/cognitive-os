"""Sealed evaluator fixtures are separate from model-visible source copies."""
from pathlib import Path

from runtime.feature_acceptance import probe, save
from runtime.feature_challenges import assertion_failure
from runtime.feature_workspace import inventory


def sources(task, value):
    return value if isinstance(value, dict) else {task.get('source_path', 'engine.py'): value}


def write_source(root, name, content):
    path = root / name
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('evaluation_source_outside_copy')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content.encode('utf-8'))


def evaluate_spec(task, spec, work, python):
    results = {}
    if not spec or not spec.get('tests'):
        return {'status': 'missing', 'score_cap': 0}
    for label, source in [('reference', task['reference']), ('original', task['original']),
                          *[(f'mutant-{i}', s) for i, s in enumerate(task['mutants'])]]:
        root = work / label / 'project'
        (root / 'tests').mkdir(parents=True)
        files = sources(task, source)
        for name, content in files.items():
            write_source(root, name, content)
        write_source(root, 'tests/test_existing.py', task['existing'])
        for row in spec['tests']:
            path = root / row['path']
            if not path.resolve().is_relative_to(root.resolve()) or row['path'] in {*files, 'tests/test_existing.py'}:
                return {'status': 'invalid_scope', 'score_cap': 0}
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(row['content'].encode())
        result = probe(root, root.parent / 'check', python,
                       [r['path'] for r in spec['tests']] + spec.get('regression_tests', []),
                       spec.get('environment', {}))
        results[label] = {**result, 'assertion_failure': assertion_failure(result)}
    good = results['reference']['returncode'] == 0 and results['reference']['counts']['passed'] > 0
    gap = results['original']['assertion_failure']
    killed = sum(results[f'mutant-{i}']['assertion_failure'] for i in range(len(task['mutants'])))
    # Strict caps are specified before inference. All numbers remain local to this synthetic suite.
    cap = 0 if not good else min(10 if gap else 4, 6 + 4 * killed / len(task['mutants']))
    summary = {'status': 'valid' if good and gap else 'invalid', 'reference_pass': good,
               'original_gap': gap, 'killed': killed, 'mutants': len(task['mutants']), 'score_cap': cap}
    save(work / 'report.json', {'summary': summary, 'executions': results})
    return summary


def evaluate_candidate(task, candidate, work, python):
    root = work / 'project'
    (root / 'tests').mkdir(parents=True)
    for name in inventory(candidate):
        if not name.startswith('tests/'):
            write_source(root, name, (candidate / name).read_text(encoding='utf-8-sig'))
    (root / 'tests/test_sealed_oracle.py').write_bytes(task['oracle'].encode())
    (root / 'tests/test_existing.py').write_bytes(task['existing'].encode())
    result = probe(root, work / 'check', python, ['tests'], {})
    save(work / 'report.json', result)
    return {'passed': result['returncode'] == 0, 'counts': result['counts']}
