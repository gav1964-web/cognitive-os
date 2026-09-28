"""Compare an unchanged model candidate on explicitly selected local input files.

Copies inputs and existing tests; does not generate domain checks or modify the
target. A passing receipt proves only the selected assertions and input corpus.
"""
import json
from pathlib import Path

from .feature_acceptance import probe, save, validate_spec
from .feature_checkpoint import load_roles, qualified_spec, verified_candidate
from .feature_workspace import (copy_source, digest, excluded, inventory,
                                materialize_edits, owned_path)


def input_inventory(project, names, expected):
    if not 1 <= len(names) <= 100 or len(set(names)) != len(names):
        raise ValueError('feature_input_count')
    result, total = {}, 0
    for name in names:
        path = owned_path(project, name)
        if (name in expected or any(excluded(p) for p in Path(name).parts)
                or path.name == 'config.json'
                or any(w in path.stem.lower() for w in ('credential', 'secret', 'token'))
                or not path.is_file()):
            raise ValueError('feature_input_not_external_data')
        total += path.stat().st_size
        if total > 100_000_000:
            raise ValueError('feature_input_byte_limit')
        result[name] = digest(path.read_bytes())
    return result


def run_corpus_checks(*, project, checkpoint, work, python, inputs, targets, timeout=300,
                      baseline_receipt=None):
    project, checkpoint, work = map(lambda p: Path(p).resolve(), (project, checkpoint, work))
    if (work.exists() or work.is_relative_to(project) or project.is_relative_to(work)
            or type(timeout) is not int or not 1 <= timeout <= 600):
        raise ValueError('feature_corpus_requires_fresh_external_workdir')
    saved = json.loads((checkpoint / 'report.json').read_text(encoding='utf-8'))
    expected = inventory(project)
    roles, _ = load_roles(checkpoint, project, expected, saved['goal'])
    spec = qualified_spec(checkpoint)['accepted']
    tests = validate_spec(spec, expected)
    candidate = verified_candidate(checkpoint)
    edits = materialize_edits(project, expected, candidate['proposal']['edits'], roles['architect']['scope'], frozen_tests=tests)
    hashes = {n: digest(b) for n, b in {**tests, **edits}.items()}
    if hashes != candidate['candidate_hashes']:
        raise ValueError('feature_corpus_candidate_changed')
    if (not 1 <= len(targets) <= 20 or len(set(targets)) != len(targets)
            or any(t.partition('::')[0] not in expected
                   or not Path(t.partition('::')[0]).name.startswith('test_')
                   or not t.partition('::')[0].endswith('.py') for t in targets)):
        raise ValueError('feature_corpus_existing_tests_required')
    corpus = input_inventory(project, inputs, expected)
    work.mkdir(parents=True)
    result = {'schema_version': 'feature_corpus_checks.v1', 'project': str(project),
              'checkpoint': str(checkpoint), 'goal': saved['goal'], 'source_hashes': expected,
              'candidate_hashes': hashes, 'input_hashes': corpus, 'targets': targets,
              'source_apply': False, 'status': 'running', 'checks': {}}
    save(work / 'report.json', result)
    for label in ('baseline', 'candidate'):
        if label == 'baseline' and baseline_receipt:
            prior = json.loads(Path(baseline_receipt).read_text(encoding='utf-8'))
            if (prior.get('schema_version') != 'feature_corpus_checks.v1'
                    or prior.get('status') != 'passed'
                    or {**prior['source_hashes'], **prior['candidate_hashes']} != expected
                    or prior['input_hashes'] != corpus or prior['targets'] != targets):
                raise ValueError('feature_corpus_baseline_receipt_mismatch')
            result['checks']['baseline'] = prior['checks']['candidate']
            result['baseline_reused_from'] = {'path': str(Path(baseline_receipt).resolve()),
                'sha256': digest(Path(baseline_receipt).read_bytes())}
            continue
        root = work / label / 'project'
        copy_source(project, root, {**expected, **corpus})
        if label == 'candidate':
            for name, body in {**tests, **edits}.items():
                path = owned_path(root, name)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(body)
        checked = probe(root, work / label / 'checks', Path(python), targets,
                        spec.get('environment', {}), timeout=timeout)
        checked['inputs_unchanged'] = all(digest(owned_path(root, n).read_bytes()) == h
                                           for n, h in corpus.items())
        result['checks'][label] = checked
        save(work / 'report.json', result)
    result['source_unchanged'] = inventory(project) == expected
    result['original_inputs_unchanged'] = input_inventory(project, inputs, expected) == corpus
    before, after = (result['checks'][k] for k in ('baseline', 'candidate'))
    result['regressions'] = [n for n, state in before['tests'].items()
                             if state == 'passed' and after['tests'].get(n) != 'passed']
    result['status'] = 'passed' if (
        result['source_unchanged'] and result['original_inputs_unchanged']
        and set(before['tests']) == set(after['tests']) and after['counts']['passed']
        and all(c['returncode'] == 0 and c['source_unchanged'] and c['inputs_unchanged']
                and not c['counts']['skipped'] for c in (before, after))) else 'blocked'
    save(work / 'report.json', result)
    return result
