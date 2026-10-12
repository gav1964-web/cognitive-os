"""Real native qualification rejects mistaken preservation before any code repair."""
import json
import sys
from pathlib import Path

import pytest

from runtime.feature_acceptance import prepare, specification_feedback
from runtime.feature_workspace import inventory
from runtime.feature_quality_chat import QualityChat
from runtime.local_inference import LocalInferenceConfig
from tests.runtime.test_feature_development import project, fake_chat
from tests.runtime.test_feature_quality import augment


def test_existing_class_regression_has_separate_native_baseline(project, tmp_path):
    from tests.runtime.test_feature_development import spec
    from plugins.development_quality.src.baseline_expectations import validate
    old = project / 'tests/test_existing.py'
    old.write_text('import unittest\nfrom engine import display\n'
        'class ExistingChecks(unittest.TestCase):\n'
        '    def test_positive(self):\n        self.assertEqual(display(3), "3")\n')
    value = spec()
    value['regression_tests'] = ['tests/test_existing.py::ExistingChecks::test_positive']
    value['baseline_expectations'] = [{'node': 'tests/test_labels.py::test_negative',
        'classification': 'feature_gap', 'reason': 'negative labels change',
        'goal_quote': 'negative labels', 'source_evidence': [{'path': 'engine.py', 'quote': 'return str(value)'}]}]
    sources = [{'path': 'engine.py', 'content': (project/'engine.py').read_text()}]
    assert validate(value, 'negative labels', sources, required=True) == []
    _, checked = prepare(project, tmp_path/'separate', inventory(project), value, Path(sys.executable))
    assert checked['baseline_expectations']['status'] == 'matched'
    assert checked['regression']['counts']['passed'] == 1
    value['baseline_expectations'].append({**value['baseline_expectations'][0],
        'node': value['regression_tests'][0], 'classification': 'preservation'})
    assert validate(value, 'negative labels', sources, required=True)


def test_fractional_string_preservation_is_rejected_even_with_other_green_tests(tmp_path):
    root = tmp_path / 'source'
    root.mkdir()
    (root / 'engine.py').write_text('def convert(value):\n    try:\n        return int(value)\n    except ValueError:\n        return None\n')
    spec = {'tests': [{'path': 'tests/test_convert.py', 'content':
        'from engine import convert\n'
        'def test_preserve_integer():\n    assert convert("3") == 3\n'
        'def test_preserve_fraction_string():\n    assert convert("3.9") == 3\n'
        'def test_new_alias():\n    assert convert("zero") == 0\n'}],
        'regression_tests': [], 'regression_policy': 'new_preservation_only',
        'acceptance': ['new alias, unchanged other coercion'], 'limitations': ['unit boundary'],
        'baseline_expectations': [{'node': 'tests/test_convert.py::' + name, 'kind': kind}
            for name, kind in [('test_preserve_integer', 'preservation'),
                               ('test_preserve_fraction_string', 'preservation'), ('test_new_alias', 'feature_gap')]]}
    before = inventory(root)
    with pytest.raises(ValueError, match='feature_baseline_expectations_not_qualified'):
        prepare(root, tmp_path / 'rejected', before, spec, Path(sys.executable))
    receipt = json.loads((tmp_path / 'rejected/baseline.json').read_text())
    assert receipt['new_tests']['counts'] == dict(passed=1, failed=2, error=0, skipped=0)
    feedback = specification_feedback(receipt)['baseline_expectations']
    assert any('fraction_string' in x and 'expected passed' in x for x in feedback['issues'])
    assert inventory(root) == before
    # Correcting preservation does not waive the independently required feature gap.
    spec['tests'][0]['content'] = spec['tests'][0]['content'].replace('convert("3.9") == 3', 'convert("3.9") is None')
    _, checked = prepare(root, tmp_path / 'qualified', before, spec, Path(sys.executable))
    assert checked['baseline_expectations']['status'] == 'matched'


def test_strict_quality_admission_cannot_omit_predictions(project, tmp_path):
    delegate, calls = fake_chat(project), []
    def transport(messages, *, config):
        calls.append(config.provider_label)
        return augment('spec_writer', delegate(messages, config=config))
    q = QualityChat(transport, tmp_path / 'quality', require_baseline_expectations=True)
    with pytest.raises(ValueError, match='quality_role_correction_limit:spec_writer'):
        q([{'role': 'system', 'content': 'spec'}, {'role': 'user', 'content': json.dumps({
            'goal': 'negative labels', 'sources': [], 'artifacts': {}})}],
            config=LocalInferenceConfig('http://unused', 'fake', provider_label='feature:spec_writer'))
    assert calls == ['feature:spec_writer'] * 3


def test_extension_cannot_silently_drop_new_expectations():
    from runtime.feature_extension import merge_extension
    from tests.runtime.test_feature_development import spec
    base = {'spec': spec(), 'test_hashes': {'tests/test_labels.py': 'frozen'}}
    extra = {'tests': [{'path': 'tests/test_extra.py', 'content': 'assert True'}],
             'acceptance': ['extra'], 'limitations': ['unit'], 'baseline_expectations': []}
    with pytest.raises(ValueError, match='complete_expectations'):
        merge_extension(base, extra)
    base['spec']['baseline_expectations'] = [{'node': 'old'}]
    extra['baseline_expectations'] = [{'node': 'new'}]
    assert merge_extension(base, extra)['baseline_expectations'] == [{'node': 'old'}, {'node': 'new'}]
