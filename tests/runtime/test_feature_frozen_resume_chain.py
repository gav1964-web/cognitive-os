"""A stop in an unqualified extension retains tests qualified before its resume."""
import json
import shutil
import sys
from pathlib import Path

import pytest

from runtime.feature_acceptance import save
from runtime.feature_development import run_feature_development
from runtime.feature_quality_chat import QualityChat
from runtime.feature_quality_resume import restore_prior_frozen
from runtime.feature_workspace import inventory
from runtime.local_inference import LocalInferenceConfig
from tests.runtime.test_feature_development import fake_chat, project, spec


@pytest.mark.parametrize('tamper', [None, 'goal', 'cycle', 'frozen'])
def test_multihop_unqualified_resume_retains_bound_frozen_evidence(project, tmp_path, tamper):
    cfg = LocalInferenceConfig('http://unused', 'fake')
    accepted = tmp_path / 'first/cycle-0'
    result = run_feature_development(project=project, work=accepted, goal='goal',
        python=Path(sys.executable), chat=fake_chat(project),
        configs={r: cfg for r in ('analyzer', 'architect', 'spec_writer')})
    assert result['status'] == 'verified'
    report = json.loads((accepted / 'report.json').read_text())
    unqualified = accepted.parent / 'cycle-1'
    last = tmp_path / 'second/cycle-0'
    for checkpoint in [unqualified, last]:
        checkpoint.mkdir(parents=True)
        for name in ['analyzer.json', 'architect.json', 'source-inventory.json']:
            shutil.copyfile(accepted / name, checkpoint / name)
        save(checkpoint / 'report.json', {
            **report, 'status': 'blocked', 'reason': 'feature_stop_requested', 'attempts': [],
            'artifacts': {k: v for k, v in report['artifacts'].items() if k in ('analyzer', 'architect')}})
    save(accepted.parent / 'report.json', {'goal': 'goal', 'source_hashes': inventory(project),
        'cycles': [{'checkpoint': str(accepted)}, {'checkpoint': str(unqualified)}]})
    journal = {'goal': 'goal', 'source_hashes': inventory(project), 'cycles': [{'checkpoint': str(last)}],
               'resumed_native_rejected_spec': str(unqualified)}
    if tamper == 'goal':
        bad = json.loads((unqualified / 'report.json').read_text())
        bad['goal'] = 'unrelated goal'
        save(unqualified / 'report.json', bad)
    elif tamper == 'cycle':
        journal['resumed_native_rejected_spec'] = str(last)
    elif tamper == 'frozen':
        bad = json.loads((accepted / 'spec_writer.json').read_text())
        bad['tests'][0]['content'] = '# edited after acceptance'
        save(accepted / 'spec_writer.json', bad)
    save(last.parent / 'report.json', journal)
    q = QualityChat(None, tmp_path / 'new')
    if tamper:
        with pytest.raises(ValueError, match='(identity_changed|cycle_or_depth|frozen_spec_mismatch)'):
            restore_prior_frozen(q, last, project, inventory(project), 'goal')
        assert not q.frozen
    else:
        restore_prior_frozen(q, last, project, inventory(project), 'goal')
        assert q.frozen == spec()['tests'] and not q.retained
        # A further stopped invocation must retain the same obligations again.
        newest = tmp_path / 'third/cycle-0'
        newest.mkdir(parents=True)
        save(newest.parent / 'report.json', {
            'goal': 'goal', 'source_hashes': inventory(project), 'cycles': [],
            'resumed_unqualified_spec': str(last)})
        again = QualityChat(None, tmp_path / 'new-again')
        restore_prior_frozen(again, newest, project, inventory(project), 'goal')
        assert again.frozen == q.frozen and not again.retained
