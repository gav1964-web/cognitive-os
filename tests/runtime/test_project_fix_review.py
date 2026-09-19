import runpy
from pathlib import Path

import pytest

from runtime.project_fix_review import review_project_fix

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('fixed,expected', [('return x.strip().lower()', 'verified'), ('return x.strip()', 'not_verified')])
def test_review_scenario_reuses_inspect_and_real_replay(tmp_path, monkeypatch, fixed, expected):
    case_factory = runpy.run_path(str(ROOT / 'packages/cognitive-replay/tests/test_replay_api.py'))['_case']
    profile_factory = runpy.run_path(str(ROOT / 'packages/cognitive-replay/tests/conftest.py'))['test_environment_profile']
    public, oracle = case_factory(tmp_path, 'def normalize(x): return x\n',
                                   f'def normalize(x): {fixed}\n',
                                   "from sample_pkg import normalize\ndef test_normalize(): assert normalize(' A ') == 'a'\n")
    profile = profile_factory(tmp_path)
    monkeypatch.setattr('runtime.project_fix_review.freeze_environment_profile', lambda **_: profile)
    result = review_project_fix(root=tmp_path, project='project', baseline=public['cases'][0]['baseline_revision'],
                                fix=oracle['cases'][0]['fix_revision'], tests=['tests/test_sample.py'],
                                production=['src/sample_pkg/__init__.py'], wheels=[], timeout=60)
    assert result['status'] == expected, result['replay']
    assert result['replay']['source_worktree_unchanged'] and result['replay']['sandbox_cleaned']
    assert result['facts']['tree']
