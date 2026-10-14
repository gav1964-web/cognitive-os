"""Same-source role resume and executable SpecWriter feedback, without target writes."""
import json
import sys
from pathlib import Path

import pytest

from runtime.feature_acceptance import save
from runtime.feature_development import run_feature_development
from runtime.feature_prompts import COMMON, ROLE
from runtime.feature_workspace import inventory
from runtime.local_inference import LocalInferenceConfig
from tests.runtime.test_feature_development import project, fake_chat, spec, run


def checkpoint(project, tmp_path):
    delegate = fake_chat(project)
    def timeout(messages, *, config):
        if config.provider_label == 'feature:spec_writer':
            raise TimeoutError('provider deadline')
        return delegate(messages, config=config)
    result = run(project, tmp_path, chat=timeout)
    assert result['status'] == 'blocked'
    old = tmp_path / 'run'
    save(tmp_path / 'transcript.json', [{'messages': [
        {'role': 'system', 'content': COMMON + ROLE['spec_writer']},
        {'role': 'user', 'content': json.dumps({'goal': result['goal'], 'sources': [
            {'path': 'engine.py', 'start': 1, 'end': 2, 'content': 'FORGED TEXT'}]})}]}])
    return old


def resume(project, tmp_path, old, chat, **kwargs):
    config = LocalInferenceConfig('http://unused', 'fake')
    return run_feature_development(project=project, work=tmp_path / 'resumed',
        goal='Improve negative display labels', python=Path(sys.executable),
        configs={'spec_writer': config}, resume_roles=old, stop_after='spec_writer',
        chat=chat, **kwargs)


def test_resume_only_calls_spec_and_qualifies_native_gap_without_writes(project, tmp_path):
    old = checkpoint(project, tmp_path)
    before = inventory(project)
    calls = []
    def chat(messages, *, config):
        calls.append(config.provider_label)
        payload = json.loads(messages[1]['content'])
        assert payload['sources'][0]['content'] == (project / 'engine.py').read_text()
        assert 'FORGED TEXT' not in messages[1]['content']
        return spec()
    result = resume(project, tmp_path, old, chat)
    assert result['status'] == 'spec_qualified', result
    assert calls == ['feature:spec_writer']
    assert result['baseline']['new_tests']['counts']['failed'] == 1
    assert result['baseline']['regression']['counts']['passed'] == 1
    assert result['frozen_test_hashes'] and not result['source_apply']
    assert inventory(project) == before and not result['attempts']


@pytest.mark.parametrize('change', ['source', 'artifact', 'goal', 'project'])
def test_stale_checkpoint_rejected_before_inference(project, tmp_path, change):
    old = checkpoint(project, tmp_path)
    if change == 'source':
        (project / 'engine.py').write_text('# changed')
    elif change == 'artifact':
        value = json.loads((old / 'architect.json').read_text())
        value['design'] = 'inconsistent'
        save(old / 'architect.json', value)
    else:
        value = json.loads((old / 'report.json').read_text())
        value[change] = 'different'
        save(old / 'report.json', value)
    calls = []
    result = resume(project, tmp_path, old, lambda *a, **k: calls.append(a))
    assert result['status'] == 'blocked' and not calls


def test_specwriter_receives_native_fixture_errors_then_corrects_own_tests(project, tmp_path):
    old = checkpoint(project, tmp_path)
    seen = []
    def chat(messages, *, config):
        payload = json.loads(messages[1]['content'])
        seen.append(payload)
        value = spec()
        if len(seen) == 1:
            value['tests'][0]['content'] = 'def test_bad():\n    raise ValueError("bad fixture")\n    assert False\n'
        else:
            feedback = payload['feedback']
            assert 'bad fixture' in str(feedback['baseline']['new_tests']['failures'])
            assert feedback['baseline']['new_tests']['assertion_failures'] == []
        return value
    result = resume(project, tmp_path, old, chat)
    assert result['status'] == 'spec_qualified'
    assert [r['status'] for r in result['spec_attempts']] == ['rejected', 'qualified']
    assert len(seen) == 2 and inventory(project) == json.loads((old / 'source-inventory.json').read_text())


def test_already_passing_spec_cannot_be_certified_after_feedback(project, tmp_path):
    old = checkpoint(project, tmp_path)
    calls = []
    def chat(*args, **kwargs):
        calls.append(1)
        value = spec()
        value['tests'][0]['content'] = 'def test_trivial():\n    assert True\n'
        return value
    result = resume(project, tmp_path, old, chat)
    assert result['status'] == 'blocked' and len(calls) == 2
    assert 'spec_writer' not in result['artifacts']


def test_resume_includes_last_read_response_even_without_a_following_request(project, tmp_path):
    from runtime.feature_checkpoint import load_roles
    old = checkpoint(project, tmp_path)
    path = tmp_path / 'transcript.json'
    calls = json.loads(path.read_text())
    payload = json.loads(calls[0]['messages'][1]['content'])
    payload['sources'] = []
    calls[0]['messages'][1]['content'] = json.dumps(payload)
    calls[0].update(status='returned', raw_response={'status': 'read', 'reads': [
        {'path': 'engine.py', 'start': 1, 'end': 2}]})
    save(path, calls)
    _, rows = load_roles(old, project, inventory(project), 'Improve negative display labels')
    assert rows[0]['content'] == (project / 'engine.py').read_text()


def test_unittest_assertions_qualify_without_new_generation_on_resume(project, tmp_path):
    old = checkpoint(project, tmp_path)
    value = spec()
    value['tests'][0]['content'] = ('import unittest\nfrom engine import display\n'
        'class TestLabel(unittest.TestCase):\n'
        '    def test_negative(self):\n        self.assertEqual(display(-2), "(2)")\n')
    report = json.loads((old / 'report.json').read_text())
    report['spec_attempts'] = [{'status': 'rejected', 'feedback': {'rejected_spec': value}}]
    save(old / 'report.json', report)
    save(old / 'spec-proposal-1.json', value)
    calls = []
    result = resume(project, tmp_path, old, lambda *a, **k: calls.append(a))
    assert result['status'] == 'spec_qualified', result
    assert not calls and result['rechecked_spec_from'] == str(old.resolve())
    from runtime.feature_checkpoint import load_roles
    _, selections = load_roles(tmp_path / 'resumed', project, inventory(project), result['goal'])
    assert selections[0]['content'] == (project / 'engine.py').read_text()


def test_generated_subject_replacement_and_oversize_have_actionable_errors(project):
    from runtime.feature_acceptance import validate_spec
    value = spec()
    value['tests'][0]['content'] = 'from unittest.mock import patch\n' + 'patch("engine.display")\n' * 401 + 'assert False\n'
    with pytest.raises(ValueError) as caught:
        validate_spec(value, inventory(project))
    assert '403 lines; limit400' in str(caught.value)
    assert 'production replacement forbidden' in str(caught.value)


def test_mock_input_fixture_runs_real_subject_and_qualifies(project, tmp_path):
    value = spec()
    value['tests'][0]['content'] = ('from unittest.mock import Mock\nfrom engine import display\n'
        'def test_negative():\n    item = Mock(value=-2)\n    assert display(item.value) == "(2)"\n')
    old = checkpoint(project, tmp_path)
    result = resume(project, tmp_path, old, lambda *a, **k: value)
    assert result['status'] == 'spec_qualified'


@pytest.mark.parametrize('replacement', ['globals()["display"] = lambda x: "(2)"',
    'display = lambda x: "(2)"', 'patch("engine.display", return_value="(2)")'])
def test_replacing_production_code_remains_forbidden(project, replacement):
    from runtime.feature_acceptance import validate_spec
    value = spec()
    value['tests'][0]['content'] = ('from unittest.mock import patch\nfrom engine import display\n'
        + replacement + '\nassert display(-2) == "(2)"\n')
    with pytest.raises(ValueError, match='production replacement forbidden'):
        validate_spec(value, inventory(project))


def test_fresh_spec_does_not_copy_rejected_test_implementation(project, tmp_path):
    old = checkpoint(project, tmp_path)
    value = spec()
    value['tests'][0]['content'] = 'def test_old():\n    assert "BAD PRIOR TEMPLATE"\n'
    report = json.loads((old / 'report.json').read_text())
    report['spec_attempts'] = [{'status': 'rejected', 'feedback': {'rejected_spec': value}}]
    save(old / 'report.json', report)
    save(old / 'spec-proposal-1.json', value)
    seen = []
    def chat(messages, *, config):
        seen.append(messages)
        assert 'BAD PRIOR TEMPLATE' not in str(messages)
        return spec()
    result = resume(project, tmp_path, old, chat, fresh_spec=True)
    assert result['status'] == 'spec_qualified' and len(seen) == 1
    assert 'rechecked_spec_from' not in result
