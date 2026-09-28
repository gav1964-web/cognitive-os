"""Exercise structured requests through the public configured role workflow."""
import json
from pathlib import Path

import pytest

from runtime.role_pipeline import run_role_pipeline


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('case_id', ['unicode_receipt', 'contradictory_order'])
def test_structured_request_reaches_final_review_without_execution(case_id):
    manifest = json.loads((ROOT / 'evaluation/upstream_roles/manifest.json').read_text(encoding='utf-8'))
    case = next(row for row in manifest['cases'] if row['id'] == case_id)
    result = run_role_pipeline(root=ROOT, project_dir=ROOT / case['project'],
                               goal=case['goal'], task_contract=case['task_contract'], write=True)
    assert result['status'] == 'ok'
    assert result['next_action'] == 'rework_role_artifacts'
    assert result['transform']['status'] == 'skipped'
    assert result['safety']['source_code_changes'] is False
    assert result['safety']['llm_invoked'] is False
    spec = json.loads(Path(result['artifacts']['technical_spec']['path']).read_text(encoding='utf-8'))
    assert spec['requirements'][0]['statement'] == case['task_contract']['requirements'][0]['statement']
    assert spec['task_handoff']['execution_authorized'] is False
    if case_id == 'contradictory_order':
        assert spec['task_handoff']['status'] == 'needs_clarification'
