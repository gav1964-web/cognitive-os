"""A selected research option must not advertise readiness for execution."""
from pathlib import Path

import pytest

import runtime.project_development_core as core

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('handoff', ['research_required', 'controlled_stop', 'needs_replanning'])
def test_planning_result_preserves_handoff_stop(tmp_path, monkeypatch, handoff):
    (tmp_path / 'main.py').write_text('def run(x):\n    return x\n')
    monkeypatch.setattr(core, '_role_chain_handoff', lambda **kw: {
        'status': handoff, 'executed': False, 'route': 'research'})
    result = core.run_project_development(root=ROOT, project_dir=tmp_path,
        goal='Assess the next project improvement', run_role_chain=True)
    assert result['decision']['status'] == 'selected'
    assert result['status'] == handoff
    assert result['experiment']['status'] == 'not_requested'
