"""Immutable-test drift must be actionable before another semantic audit."""
from copy import deepcopy
import json

import pytest

from runtime.feature_quality_chat import QualityChat
from runtime.feature_quality_draft import frozen_test_mismatches
from runtime.local_inference import LocalInferenceConfig
from tests.runtime.test_feature_development import spec
from tests.runtime.test_feature_quality import augment


@pytest.mark.parametrize('actual', ['prefix\nwrong\n', 'prefix\r\ncorrect\n', 'prefix\ncorrect\nextra'])
def test_drift_reports_exact_context_including_line_endings(actual):
    frozen = [{'path': 'tests/test_value.py', 'content': 'prefix\ncorrect\n'}]
    before = deepcopy(frozen)
    result = frozen_test_mismatches(frozen, {'tests/test_value.py': actual})
    assert result[0]['path'] == frozen[0]['path']
    assert result[0]['expected_context'] == frozen[0]['content']
    assert result[0]['actual_context'] == actual
    assert result[0]['actual_sha256'] != result[0]['expected_sha256']
    assert frozen == before


def test_missing_test_has_explicit_path_and_no_fabricated_content():
    result = frozen_test_mismatches([{'path': 'tests/test_value.py', 'content': 'pass\n'}], {})
    assert result[0]['path'] == 'tests/test_value.py'
    assert result[0]['actual_sha256'] is None
    assert 'expected_context' not in result[0]


def test_model_receives_precise_drift_and_only_corrected_bytes_reach_audit(tmp_path):
    accepted = augment('spec_writer', spec())
    altered = deepcopy(accepted)
    altered['tests'][0]['content'] += '\n# unwanted change\n'
    calls = []

    def chat(messages, *, config):
        calls.append(config.provider_label)
        payload = json.loads(messages[1]['content'])
        if len(calls) == 1:
            return deepcopy(altered)
        if len(calls) == 2:
            issues = payload['quality_contract_feedback']['issues']
            rows = next(i['immutable_test_mismatches'] for i in issues if isinstance(i, dict) and 'immutable_test_mismatches' in i)
            assert rows[0]['path'] == accepted['tests'][0]['path']
            assert '# unwanted change' in rows[0]['actual_context']
            assert 'unwanted' not in rows[0]['expected_context']
            return deepcopy(accepted)
        assert config.provider_label == 'quality:spec_auditor'
        assert payload['specification']['tests'] == accepted['tests']
        return {'decision': 'approve'}

    q = QualityChat(chat, tmp_path)
    q.frozen = deepcopy(accepted['tests'])
    cfg = LocalInferenceConfig('http://unused', 'fake', provider_label='feature:spec_writer')
    payload = {'goal': 'labels', 'sources': [], 'artifacts': {'architect': {}}}
    result = q([{'role': 'system', 'content': 'spec'},
                {'role': 'user', 'content': json.dumps(payload)}], config=cfg)
    assert result == accepted and q.frozen == accepted['tests']
    assert altered['tests'][0]['content'].endswith('# unwanted change\n')
    assert calls == ['feature:spec_writer', 'feature:spec_writer', 'quality:spec_auditor']
