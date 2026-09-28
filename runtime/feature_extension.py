"""Extend qualified acceptance without rewriting its already verified cases."""
import json
from pathlib import Path

from .feature_checkpoint import qualified_spec
from .feature_acceptance import MAX_TEST_FILES


def load_extension(prior, *, depth=0):
    if depth > 8:
        raise ValueError('feature_extension_checkpoint_chain_limit')
    prior = Path(prior)
    frozen = qualified_spec(prior)
    report = json.loads((prior / 'report.json').read_text(encoding='utf-8'))
    if not frozen:
        inherited = report.get('inherited_specification')
        if not inherited:
            raise ValueError('feature_extension_requires_qualified_spec')
        origin = Path(inherited['checkpoint'])
        other = json.loads((origin / 'report.json').read_text(encoding='utf-8'))
        if (any(report[k] != other[k] for k in ('goal', 'project')) or
                json.loads((prior / 'source-inventory.json').read_text()) !=
                json.loads((origin / 'source-inventory.json').read_text())):
            raise ValueError('feature_extension_checkpoint_identity_changed')
        base = load_extension(origin, depth=depth + 1)
        if base['test_hashes'] != inherited['test_hashes']:
            raise ValueError('feature_extension_checkpoint_hashes_changed')
        return base
    return {'spec': frozen['accepted'], 'baseline': report['baseline'],
            'test_hashes': report['frozen_test_hashes']}


def extension_context(base):
    return {'accepted_contract': {k: v for k, v in base['spec'].items() if k not in ('tests', 'cases')},
            'frozen_test_hashes': base['test_hashes'],
            'remaining_test_files': MAX_TEST_FILES - len(base['test_hashes']),
            'instruction': 'Extend the accepted specification to cover currently untested design integration through existing public APIs. '
            'Return ONLY new Python test files, not copies or rewrites of inherited tests. '
            'Use real production behavior and concrete input fixtures. New tests themselves must include '
            'a desired feature assertion that fails now and a preservation test that passes now. '
            'The inherited tests and regression targets are retained automatically. '
            'Read source for object construction and caller conventions when needed. '
            'State accurate remaining limitations after adding your tests; do not claim binary/UI evidence.'}


def merge_extension(base, extra):
    inherited = base['spec']
    tests = extra.get('tests', [])
    if not tests or any(t['path'] in base['test_hashes'] for t in tests):
        raise ValueError('feature_extension_cannot_replace_frozen_tests')
    if extra.get('environment', {}) != inherited.get('environment', {}):
        raise ValueError('feature_extension_environment_changed')
    if not extra.get('acceptance') or not extra.get('limitations'):
        raise ValueError('feature_extension_acceptance_and_limits_required')
    return {**inherited, 'tests': [*inherited['tests'], *tests],
            'acceptance': [*inherited['acceptance'], *extra['acceptance']],
            'limitations': extra['limitations'],
            'regression_tests': list(dict.fromkeys([
                *inherited['regression_tests'], *extra.get('regression_tests', [])])),
            'test_authoring': {**inherited.get('test_authoring', {}),
                               'extension_python': 'COS SpecWriter model'}}


def verify_extension(base, baseline):
    before = base['baseline']['new_tests']['tests']
    observed = baseline['new_tests']['tests']
    if any(observed.get(name) != status for name, status in before.items()):
        raise ValueError('feature_extension_changed_inherited_baseline')
    added = {name: status for name, status in observed.items() if name not in before}
    assertions = set(baseline['new_tests']['assertion_failures'])
    if (not any(status == 'passed' for status in added.values())
            or not any(status == 'failed' and name in assertions for name, status in added.items())):
        raise ValueError('feature_extension_requires_own_gap_and_preservation')
