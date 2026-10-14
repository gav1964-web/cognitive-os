"""Compressed review evidence must reconstruct every omitted baseline outcome."""
import pytest
import json

from runtime.feature_acceptance import review_baseline_context
from tests.runtime.test_feature_development import project, fake_chat, run


@pytest.mark.parametrize('changed', [None, 'regression_failure', 'overlap', 'missing', 'unverified'])
def test_only_identical_disjoint_green_outcomes_can_be_referenced(changed):
    baseline = {'new_tests': {'tests': {'new::gap': 'failed'}, 'output_tail': 'trace'},
                'regression': {'tests': {'old::preserved': 'passed'}, 'output_tail': 'log'}}
    checked = {'passed': True, 'tests': {'new::gap': 'passed', 'old::preserved': 'passed'}}
    if changed == 'regression_failure': baseline['regression']['tests']['old::preserved'] = 'failed'
    if changed == 'overlap': baseline['new_tests']['tests']['old::preserved'] = 'passed'
    if changed == 'missing': checked['tests'].pop('old::preserved')
    if changed == 'unverified': checked['passed'] = False
    result = review_baseline_context(baseline, checked)
    assert 'output_tail' not in result['regression']
    if changed:
        assert result['regression']['tests'] == baseline['regression']['tests']
    else:
        assert 'tests' not in result['regression']
        reconstructed = {k: v for k, v in checked['tests'].items() if k not in baseline['new_tests']['tests']}
        assert reconstructed == baseline['regression']['tests']
    assert 'tests' in baseline['regression']


def test_reviewer_selected_reads_replace_inferred_context_without_losing_evidence(project, tmp_path):
    with (project / 'engine.py').open('a') as stream:
        stream.write('\ndef other():\n    return 7\n')
    delegate = fake_chat(project)
    rounds = {'analyzer': 0, 'reviewer': 0}
    def chat(messages, *, config):
        role = config.provider_label.split(':')[-1]
        payload = json.loads(messages[1]['content'])
        if role == 'analyzer':
            rounds[role] += 1
            if rounds[role] == 1:
                return {'status': 'read', 'reads': [{'path': 'engine.py', 'start': 1, 'end': 5}]}
            value = delegate(messages, config=config)
            value['evidence'] = [{'path': 'engine.py', 'start': 1, 'end': 5}]
            return value
        if role == 'reviewer':
            rounds[role] += 1
            assert payload['proposal']['edits'] and payload['artifacts']['spec_writer']['tests']
            assert payload['verification']['passed'] is True
            if rounds[role] == 1:
                assert 'def other' in payload['sources'][0]['content']
                return {'status': 'read', 'reads': [{'path': 'engine.py', 'start': 1, 'end': 2}]}
            if rounds[role] == 2:
                assert [(r['start'], r['end']) for r in payload['sources']] == [(1, 2)]
                return {'status': 'read', 'reads': [{'path': 'engine.py', 'start': 4, 'end': 5}]}
            assert 'def other' in ''.join(r['content'] for r in payload['sources'])
        return delegate(messages, config=config)
    result = run(project, tmp_path, chat=chat)
    assert result['status'] == 'verified' and rounds['reviewer'] == 3
    saved = json.loads((tmp_path / 'run/source-context.json').read_text())
    assert saved['sources'][0]['content'] == (project / 'engine.py').read_text()
