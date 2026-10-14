"""A native-rejected spec resumes through fresh tests without repeating analysis."""
import json
import sys
from pathlib import Path

from runtime.feature_quality import run_quality_development
from runtime.local_inference import LocalInferenceConfig
from tests.runtime.test_feature_development import project, fake_chat
from tests.runtime.test_feature_quality import augment


def test_native_rejection_is_repaired_after_resume(project,tmp_path):
    delegate=fake_chat(project)
    calls=[]
    bad=True
    def chat(messages,*,config):
        role=config.provider_label.partition(':')[2]
        calls.append(role)
        if role in ('design_auditor','spec_auditor'):
            return {'decision':'approve'}
        value=augment(role,delegate(messages,config=config))
        if role=='spec_writer' and bad:
            value['tests'][0]['content']='def test_negative():\n    assert {}["missing"] == 1\n'
        return value
    cfg=LocalInferenceConfig('http://unused','fake')
    kwargs=dict(project=project,goal='negative labels',python=Path(sys.executable),chat=chat,
        configs={r:cfg for r in ('analyzer','architect','spec_writer')},challenges=False)
    first=run_quality_development(work=tmp_path/'first',max_cycles=1,**kwargs)
    assert first['status']=='blocked'
    checkpoint=tmp_path/'first/cycle-0'
    native=json.loads((checkpoint/'report.json').read_text())
    assert native['reason']=='feature_baseline_not_qualified'
    bad=False
    calls.clear()
    result=run_quality_development(work=tmp_path/'second',resume_roles=checkpoint,**kwargs)
    assert result['status']=='verified',result
    assert 'analyzer' not in calls and 'architect' not in calls
    assert 'spec_writer' in calls and 'reviewer' in calls
    assert result['resumed_native_rejected_spec']==str(checkpoint)
    assert result['source_unchanged']
