"""A behavioral review must become a regression before another repair is accepted."""
import json
import sys
from pathlib import Path

from runtime.feature_quality import run_quality_development
from runtime.local_inference import LocalInferenceConfig
from tests.runtime.test_feature_development import project, fake_chat, spec
from tests.runtime.test_feature_quality import augment


def test_review_counterexample_automatically_freezes_discriminating_test(project, tmp_path):
    delegate = fake_chat(project)
    calls, reviews, writers = [], [], []
    def chat(messages, *, config):
        role = config.provider_label.partition(':')[2]
        calls.append(role)
        if role in ('design_auditor', 'spec_auditor'):
            return {'decision': 'approve'}
        value = augment(role, delegate(messages, config=config))
        if role == 'spec_writer':
            writers.append(1)
            if len(writers) > 1:
                value['tests'].append({'path':'tests/test_zero.py','content':
                    'from engine import display\ndef test_zero():\n    assert display(0) == "zero"\n'})
        if role == 'programmer' and len(writers) > 1:
            value['edits'][0]['replacements'][0]['new'] = (
                'return "zero" if value == 0 else (f"({-value})" if value < 0 else str(value))')
        if role == 'reviewer':
            reviews.append(1)
            value['goal_complete'] = True
            if len(reviews) == 1:
                value.update(decision='reject', repair_owner='programmer', reason='zero label missing',
                    counterexamples=[{'input':0,'expected':'zero','observed':'0',
                                      'goal_clause':'zero is labelled zero'}])
        return value
    cfg = LocalInferenceConfig('http://unused','fake')
    work = tmp_path/'quality'
    result = run_quality_development(project=project, work=work,
        goal='negative labels are parenthesized, zero is labelled zero',
        python=Path(sys.executable), chat=chat, challenges=False,
        configs={r:cfg for r in ('analyzer','architect','spec_writer')})
    assert result['status']=='verified', result
    witness = json.loads((work/'spec-witness-1/1/report.json').read_text())
    assert witness['status']=='witness_found' and not witness['grants_approval']
    accepted = json.loads((Path(result['checkpoint'])/'spec_writer.json').read_text())
    assert accepted['tests'][0] == spec()['tests'][0]
    assert accepted['tests'][1]['path']=='tests/test_zero.py'
    first_review = calls.index('reviewer')
    assert calls[first_review+1] == 'spec_writer'
    assert result['source_unchanged']
