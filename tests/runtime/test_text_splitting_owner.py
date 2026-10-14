"""Frozen source proposals and read-only admission for the text owner."""
import json
from pathlib import Path

import pytest

from runtime.competency_knowledge import invoke_knowledge
from runtime.helper_proposal import validate_helper_proposal

ROOT = Path(__file__).resolve().parents[2]
CASES = json.loads((ROOT / 'tests/fixtures/text_splitting_legacy.json').read_text(encoding='utf-8'))['cases']


@pytest.mark.parametrize('case', CASES, ids=[c['id'] for c in CASES])
def test_registered_proposals_match_frozen_algorithm(case):
    expected = case['patch']
    raw = invoke_knowledge('text_splitting', {'operation':'propose_patch', **case['request']})
    assert raw == {'status':'proposed' if expected is not None else 'not_applicable', 'patch':expected}
    result = invoke_knowledge('text_splitting', {'operation':'propose_helper', **case['request']})
    proposal = validate_helper_proposal(result['proposal'])
    assert proposal['source'] == (expected['source'] if expected else None)
    assert proposal['operation_details'] == ({k:expected[k] for k in ('text_expression','split_line')} if expected else {})
    assert proposal['reason'] == (None if expected else 'splitlines_helper_pattern_not_proven')


@pytest.mark.parametrize('payload', [
    {'operation':'propose_helper','source':'pass'},
    {'operation':'patch_recipes','source_apply':True},
    {'operation':'boundary_profiles'},
])
def test_contract_rejects_missing_inputs_and_foreign_authority(payload):
    with pytest.raises(ValueError, match='text_splitting.input'):
        invoke_knowledge('text_splitting', payload)
