import json
from copy import deepcopy
from pathlib import Path
import sys

from runtime.feature_quality_chat import QualityChat
from runtime.feature_quality_draft import draft_binding
from runtime.feature_quality import run_quality_development
from runtime.local_inference import LocalInferenceConfig
from runtime.feature_workspace import inventory
from tests.runtime.test_feature_development import fake_chat, project
from tests.runtime.test_feature_quality import augment


def test_metadata_repair_keeps_tests_and_still_runs_audit(tmp_path):
    from tests.runtime.test_feature_development import spec
    raw = augment('spec_writer', spec())
    raw['regression_tests'] = []
    before = deepcopy(raw)
    calls = []
    def transport(messages, *, config):
        calls.append(config.provider_label)
        if config.provider_label == 'feature:spec_writer':
            return deepcopy(raw)
        payload = json.loads(messages[1]['content'])
        assert payload['specification']['regression_policy'] == 'new_preservation_only'
        return {'decision': 'approve'}
    q = QualityChat(transport, tmp_path, expected={'engine.py': 'hash'})
    payload = {'goal': 'labels', 'sources': [], 'artifacts': {'architect': {}}}
    result = q([{'role': 'system', 'content': 'spec'}, {'role': 'user', 'content': json.dumps(payload)}],
               config=LocalInferenceConfig('http://unused', 'fake', provider_label='feature:spec_writer'))
    assert result['tests'] == before['tests'] and raw == before
    assert calls == ['feature:spec_writer', 'quality:spec_auditor']
    receipt = json.loads((tmp_path / 'spec-metadata-0-0.json').read_text())
    assert receipt['original'] == before and receipt['grants_approval'] is False


def test_missing_metadata_resumes_without_writer_but_requires_native_checks(project, tmp_path):
    (project / 'tests/test_existing.py').unlink()
    delegate = fake_chat(project)
    calls = []
    def chat(messages, *, config):
        role = config.provider_label.partition(':')[2]
        calls.append(role)
        if role in ('design_auditor', 'spec_auditor'):
            return {'decision': 'approve'}
        value = augment(role, delegate(messages, config=config))
        if role == 'spec_writer':
            value['regression_tests'] = []
            value['tests'][0]['content'] += '\ndef test_positive():\n    assert display(3) == "3"\n'
        return value
    cfg = LocalInferenceConfig('http://unused', 'fake')
    kwargs = dict(project=project, goal='negative labels', python=Path(sys.executable),
        chat=chat, configs={r: cfg for r in ('analyzer', 'architect', 'spec_writer')}, challenges=False)
    # Create a genuine pre-repair rejection with the ordinary native workflow.
    from runtime.feature_development import run_feature_development
    checkpoint = tmp_path / 'historical/cycle-0'
    old = run_feature_development(work=checkpoint, max_spec_attempts=1,
                                 **{k: v for k, v in kwargs.items() if k != 'challenges'})
    assert old['reason'] == 'feature_existing_regression_required'
    original = (checkpoint / 'spec-proposal-1.json').read_bytes()
    calls.clear()
    result = run_quality_development(work=tmp_path / 'resumed', resume_roles=checkpoint, **kwargs)
    assert result['status'] == 'verified', result
    assert 'spec_writer' not in calls and 'spec_auditor' in calls
    report = json.loads((tmp_path / 'resumed/cycle-0/report.json').read_text())
    assert report['baseline']['new_tests']['counts']['failed'] == 1
    assert report['baseline']['new_tests']['counts']['passed'] == 1
    assert (checkpoint / 'spec-proposal-1.json').read_bytes() == original
    assert result['source_unchanged']
