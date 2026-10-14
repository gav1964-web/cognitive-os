"""Execute independent fault witnesses; a crash never counts as a killed mutant."""
from pathlib import Path

from .feature_acceptance import probe, save, validate_spec
from .feature_workspace import copy_source, digest, inventory, materialize_edits, owned_path


def assertion_failure(result):
    return (result['returncode'] == 1 and result['counts']['failed'] > 0
            and result['counts']['error'] == result['counts']['skipped'] == 0
            and len(result['assertion_failures']) == result['counts']['failed']
            and result['source_unchanged'])


def check_challenges(*, candidate, work, python, specification, allowed, challenges):
    candidate, work = Path(candidate).resolve(), Path(work).resolve()
    if work.exists() or work.is_relative_to(candidate) or candidate.is_relative_to(work):
        raise ValueError('challenge_fresh_external_workspace_required')
    if not isinstance(challenges, list) or not 1 <= len(challenges) <= 3:
        raise ValueError('challenge_requires_1_to_3_variants')
    expected = inventory(candidate)
    frozen = {t['path']: owned_path(candidate, t['path']).read_bytes() for t in specification['tests']}
    targets = [*frozen, *specification['regression_tests']]
    result = {'status': 'inconclusive', 'candidate_hashes': expected, 'variants': []}
    work.mkdir(parents=True)
    for i, challenge in enumerate(challenges):
        row = {'id': challenge.get('id'), 'reason': challenge.get('reason'), 'status': 'invalid'}
        folder = work / str(i)
        try:
            witnesses = []
            for j, witness in enumerate(challenge['oracle_tests']):
                name, suffix = witness['path'], 0
                while name in expected or any(t['path'] == name for t in witnesses):
                    suffix += 1
                    name = f'tests/test_cos_fault_witness_{i}_{j}_{suffix}.py'
                witnesses.append({**witness, 'path': name})
            row['witness_paths'] = {w['path']: x['path'] for w, x in zip(challenge['oracle_tests'], witnesses)}
            oracle_spec = {'tests': witnesses, 'regression_tests': list(frozen),
                           'acceptance': [challenge['reason']], 'limitations': ['local fault witness']}
            oracle = validate_spec(oracle_spec, expected)
            edits = materialize_edits(candidate, expected, challenge['edits'], allowed, frozen_tests=frozen)
            if not edits:
                raise ValueError('challenge_empty_mutation')
            for label, changes in [('reference', oracle), ('mutant', {**oracle, **edits})]:
                root = folder / label / 'project'
                copy_source(candidate, root, expected)
                for name, body in changes.items():
                    path = owned_path(root, name)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(body)
                observed = probe(root, folder / label / 'witness', Path(python), list(oracle), {})
                row[label + '_oracle'] = observed
                if label == 'mutant':
                    row['acceptance'] = probe(root, folder / label / 'acceptance', Path(python),
                                               targets, specification.get('environment', {}))
            good, bad, tested = row['reference_oracle'], row['mutant_oracle'], row['acceptance']
            valid = (good['returncode'] == 0 and good['counts']['passed'] > 0
                     and good['counts']['skipped'] == 0 and good['source_unchanged']
                     and assertion_failure(bad) and set(good['tests']) == set(bad['tests']))
            if valid and assertion_failure(tested):
                row['status'] = 'killed'
            elif valid and tested['returncode'] == 0 and tested['counts']['passed'] > 0 and tested['source_unchanged'] and not tested['counts']['skipped']:
                row['status'] = 'survived'
            else:
                row['reason_invalid'] = 'oracle or acceptance execution does not establish a valid fault'
            row['oracle_hashes'] = {n: digest(b) for n, b in oracle.items()}
        except (ValueError, KeyError, SyntaxError, TypeError, OSError) as exc:
            row['reason_invalid'] = str(exc)
        result['variants'].append(row)
    result['source_unchanged'] = inventory(candidate) == expected
    states = [r['status'] for r in result['variants']]
    if result['source_unchanged'] and 'invalid' not in states:
        result['status'] = 'passed' if set(states) == {'killed'} else 'needs_specification'
    save(work / 'report.json', result)
    return result
