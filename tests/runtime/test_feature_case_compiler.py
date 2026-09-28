"""Real target calls from model-authored data contracts, not simulated algorithms."""
import json
import sys
from pathlib import Path

import pytest

from runtime.feature_case_compiler import compile_cases
from runtime.feature_development import run_feature_development
from runtime.feature_workspace import inventory
from runtime.local_inference import LocalInferenceConfig
from tests.runtime.test_feature_development import project, fake_chat


@pytest.fixture(autouse=True)
def annotate_fixture_api(project):
    path = project / 'engine.py'
    path.write_text(path.read_text().replace('def display(value):', 'def display(value: int) -> str:'))


def spec():
    return {'status': 'ready', 'acceptance': ['negative labels; preserve positive'],
        'limitations': ['data interface only; no UI'], 'environment': {},
        'regression_tests': ['tests/test_existing.py'], 'cases': [
            {'id': 'negative', 'baseline': 'fails', 'entrypoint': 'engine.display', 'args': [-2],
             'checks': [{'path': [], 'op': 'equals', 'expected': '(2)'}]},
            {'id': 'positive', 'baseline': 'passes', 'entrypoint': 'engine.display', 'args': [2],
             'checks': [{'path': [], 'op': 'equals', 'expected': '2'}]}]}


def run(project, tmp_path, value):
    delegate = fake_chat(project)
    def chat(messages, *, config):
        if config.provider_label == 'feature:spec_writer':
            assert 'JSON call contracts' in messages[0]['content']
            return value
        return delegate(messages, config=config)
    cfg = LocalInferenceConfig('http://unused', 'fake')
    return run_feature_development(project=project, work=tmp_path / 'run',
        goal='Improve labels', python=Path(sys.executable), chat=chat,
        configs={r: cfg for r in ('analyzer', 'architect', 'spec_writer')},
        spec_format='json_calls', stop_after='spec_writer', max_spec_attempts=1)


def test_native_data_contract_has_real_gap_and_preservation_without_target_writes(project, tmp_path):
    before = inventory(project)
    value = spec()
    result = run(project, tmp_path, value)
    assert result['status'] == 'spec_qualified', result
    assert result['baseline']['new_tests']['counts'] == {'passed': 1, 'failed': 1, 'error': 0, 'skipped': 0}
    assert result['baseline']['regression']['counts']['passed'] == 1
    accepted = result['artifacts']['spec_writer']
    assert accepted['cases'] == value['cases'] and accepted['test_authoring']['cases_and_expectations'] == 'COS SpecWriter model'
    assert accepted['tests'][0]['path'] not in inventory(project) and inventory(project) == before


@pytest.mark.parametrize('entrypoint', ['os.remove', 'engine.not_created', 'engine._private', 'engine.display.__call__'])
def test_only_existing_public_functions_within_design_can_be_compiled(project, entrypoint):
    value = spec()
    value['cases'][0]['entrypoint'] = entrypoint
    with pytest.raises(ValueError):
        compile_cases(project, inventory(project), value, ['engine.py'])


def test_missing_expected_output_is_assertion_not_fixture_error(project, tmp_path):
    with (project / 'engine.py').open('a') as stream:
        stream.write('\ndef project(value: int) -> dict:\n    return {"items": [value]}\n')
    value = spec()
    value['cases'] = [{'id': 'missing', 'baseline': 'fails', 'entrypoint': 'engine.project', 'args': [3],
                      'checks': [{'path': ['items', 1], 'op': 'equals', 'expected': 4}]},
                     {'id': 'present', 'baseline': 'passes', 'entrypoint': 'engine.project', 'args': [3],
                      'checks': [{'path': ['items', 0], 'op': 'equals', 'expected': 3}]}]
    result = run(project, tmp_path, value)
    assert result['status'] == 'spec_qualified', result
    assert len(result['baseline']['new_tests']['assertion_failures']) == 1
    assert result['authors']['test_scaffolding'] == 'runtime.feature_case_compiler'


def test_data_cannot_inject_python_and_all_green_does_not_qualify(project, tmp_path):
    value = spec()
    text = '\"\nraise RuntimeError("injected")\n#'
    value['cases'][0] = {'id': 'literal', 'baseline': 'fails', 'entrypoint': 'engine.display', 'args': [text],
                        'checks': [{'path': [], 'op': 'equals', 'expected': text}]}
    result = run(project, tmp_path, value)
    assert result['reason'] == 'feature_baseline_not_qualified'
    baseline = json.loads((tmp_path / 'run/acceptance/baseline.json').read_text())
    assert baseline['new_tests']['counts'] == {'passed': 2, 'failed': 0, 'error': 0, 'skipped': 0}


def test_qualified_spec_handoff_reuses_frozen_tests_without_specwriter_call(project, tmp_path):
    original = run(project, tmp_path, spec())
    cfg = LocalInferenceConfig('http://unused', 'fake')
    seen = []
    delegate = fake_chat(project)
    def chat(messages, *, config):
        seen.append(config.provider_label)
        payload = json.loads(messages[1]['content'])
        presented = payload['artifacts']['spec_writer']
        assert 'cases' not in presented
        assert presented['tests'] == original['artifacts']['spec_writer']['tests']
        return delegate(messages, config=config)
    result = run_feature_development(project=project, work=tmp_path / 'next',
        goal='Improve labels', python=Path(sys.executable), chat=chat,
        configs={'spec_writer': cfg}, resume_roles=tmp_path / 'run', spec_format='json_calls')
    assert result['status'] == 'verified', result
    assert seen == ['feature:programmer', 'feature:reviewer']
    assert result['frozen_test_hashes'] == original['frozen_test_hashes']


def test_menu_excludes_object_interfaces_and_resolves_ids_from_source(project):
    from runtime.feature_case_catalog import case_catalog
    with (project / 'engine.py').open('a') as stream:
        stream.write('\ndef opaque(entity: object) -> dict:\n    return {}\n')
    menu = case_catalog(project, inventory(project), ['engine.py'])
    assert [row['entrypoint'] for row in menu] == ['engine.display']
    value = spec()
    for case in value['cases']:
        case.pop('entrypoint')
        case['api'] = 'api_0'
    compiled = compile_cases(project, inventory(project), value, ['engine.py'])
    assert "MODULE = 'engine'" in compiled['tests'][0]['content']


def test_json_branch_of_object_union_is_eligible_but_path_resource_is_not(project):
    from runtime.feature_case_catalog import case_catalog
    with (project / 'engine.py').open('a') as stream:
        stream.write('\ndef shape(value: object | dict) -> dict:\n    return value\n'
                     '\ndef resource(value: str | Path) -> dict:\n    return {}\n')
    menu = case_catalog(project, inventory(project), ['engine.py'])
    assert [r['entrypoint'] for r in menu] == ['engine.display', 'engine.shape']


def test_invalid_selector_cannot_be_mistaken_for_a_product_gap(project):
    value = spec()
    value['cases'][0]['checks'][0]['path'] = [-1]
    with pytest.raises(ValueError, match='check_invalid'):
        compile_cases(project, inventory(project), value, ['engine.py'])


def test_complete_menu_bodies_and_observed_regressions_are_source_bound(project, tmp_path):
    from runtime.feature_case_catalog import case_catalog, contract_sources
    from runtime.feature_checkpoint import observed_regressions
    result = run(project, tmp_path, spec())
    assert result['status'] == 'spec_qualified'
    expected = inventory(project)
    observed = observed_regressions(tmp_path / 'run', expected)
    assert observed['files'] == ['tests/test_existing.py']
    rows = contract_sources(project, expected, case_catalog(project, expected, ['engine.py']))
    assert 'return str(value)' in rows[0]['content']
