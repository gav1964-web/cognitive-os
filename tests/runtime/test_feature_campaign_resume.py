"""A new paid invocation must not forget previously witnessed fault obligations."""
import json
import sys
from pathlib import Path

import pytest

from runtime.feature_quality_challenge import restore_campaign
from runtime.feature_quality import run_quality_development
from runtime.local_inference import LocalInferenceConfig
from tests.runtime.test_feature_development import project, fake_chat
from tests.runtime.test_feature_quality import augment
from tests.runtime.test_feature_quality_challenge import (
    test_invalid_fault_is_repaired_automatically_and_candidate_is_unchanged as _seed)


def test_resume_rechecks_fixed_campaign_without_another_challenger(project, tmp_path):
    _seed(project, tmp_path)
    checkpoint = tmp_path / 'quality/cycle-0'
    campaign, hashes = restore_campaign(checkpoint)
    assert len(campaign['challenges']) == 1 and 'engine.py' in hashes
    delegate, calls = fake_chat(project), []
    def chat(messages, *, config):
        role = config.provider_label.partition(':')[2]
        calls.append(role)
        assert role != 'challenger'
        return augment(role, delegate(messages, config=config))
    cfg = LocalInferenceConfig('http://unused', 'fake')
    result = run_quality_development(project=project, work=tmp_path / 'resumed',
        goal='negative labels', python=Path(sys.executable), chat=chat,
        configs={r: cfg for r in ('analyzer', 'architect', 'spec_writer')}, resume_roles=checkpoint)
    assert result['status'] == 'verified', result
    assert result['challenge_status'] == 'passed' and calls == ['reviewer']
    restored_again, _ = restore_campaign(Path(result['checkpoint']))
    assert restored_again == campaign
    retained = tmp_path / 'quality/challenges-0-retained.json'
    data = json.loads(retained.read_text())
    data['candidate_hashes']['engine.py'] = 'wrong'
    retained.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='quality_campaign_resume_binding'):
        restore_campaign(checkpoint)


def test_unaccepted_extension_retains_earlier_candidate_faults(project, tmp_path):
    _seed(project, tmp_path)
    checkpoint = tmp_path / 'quality/cycle-0'
    campaign, hashes = restore_campaign(checkpoint)
    later = tmp_path / 'quality/cycle-1'; later.mkdir()
    source = json.loads((checkpoint / 'report.json').read_text())
    pending = {'goal': source['goal'], 'project': source['project'], 'attempts': [], 'status': 'blocked'}
    (later / 'report.json').write_text(json.dumps(pending))
    (later / 'source-inventory.json').write_bytes((checkpoint / 'source-inventory.json').read_bytes())
    journal = checkpoint.parent / 'report.json'
    data = json.loads(journal.read_text())
    data['cycles'].append({'checkpoint': str(later), 'status': 'blocked'})
    journal.write_text(json.dumps(data))
    assert restore_campaign(later) == (campaign, hashes)
    pending['goal'] = 'changed goal'
    (later / 'report.json').write_text(json.dumps(pending))
    with pytest.raises(ValueError, match='quality_campaign_resume_identity'):
        restore_campaign(later)
