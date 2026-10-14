import copy
import json
from pathlib import Path

import pytest
from jsonschema import validate

from plugins.development_quality.src.main import run


def request():
    return {'action': 'revise_preservation_assertions', 'goal': 'Keep conversions unchanged.',
        'sources': [{'path': 'engine.py', 'content': 'return int(value)'}],
        'artifact': {'tests': [{'path': 'tests/test_value.py', 'content':
            'def test_value():\n    actual = convert("3.9")\n    assert actual == {"v": 3, "other": 4}\n'}]},
        'proposal': {'decision': 'propose_revision', 'reason': 'string conversion',
            'goal_quote': 'conversions unchanged',
            'source_evidence': [{'path': 'engine.py', 'quote': 'int(value)'}],
            'corrections': [{'path': 'tests/test_value.py', 'node': 'test_value',
                'old': 'assert actual == {"v": 3, "other": 4}',
                'new': 'assert actual == {"v": None, "other": 4}', 'reason': 'preservation'}]}}


def test_revision_is_proposal_and_keeps_fixture_and_other_fields():
    payload = request()
    original = copy.deepcopy(payload)
    result = run(payload)
    schemas = Path(__file__).parents[1] / 'schemas'
    validate(payload, json.loads((schemas / 'input.json').read_text(encoding='utf-8')))
    validate(result, json.loads((schemas / 'output.json').read_text(encoding='utf-8')))
    assert not result['grants_approval']
    assert payload == original
    assert result['artifact']['tests'][0]['content'] == original['artifact']['tests'][0]['content'].replace(
        '"v": 3', '"v": None')


@pytest.mark.parametrize('replacement', [
    'assert True', 'assert actual != {"v": None, "other": 4}',
    'assert actual == {"v": None}', 'assert other == {"v": None, "other": 4}',
    'assert actual == {"v": None, "other": 4}\nraise SystemExit(0)',
    'assert actual == actual', 'assert actual == {"renamed": None, "other": 4}',
    'assert actual == {"v": None, "other": 4}, "changed message"',
])
def test_revision_cannot_delete_or_weaken_assertions_or_edit_calls(replacement):
    payload = request()
    payload['proposal']['corrections'][0]['new'] = replacement
    with pytest.raises((ValueError, SyntaxError)):
        run(payload)


@pytest.mark.parametrize('field,value', [('goal_quote', 'invented clause'),
    ('source_evidence', [{'path': 'engine.py', 'quote': 'invented behavior'}])])
def test_revision_requires_exact_goal_and_source_evidence(field, value):
    payload = request()
    payload['proposal'][field] = value
    with pytest.raises(ValueError, match='evidence_required'):
        run(payload)


def test_assertion_text_in_string_is_not_a_revision_target():
    payload = request()
    payload['artifact']['tests'][0]['content'] = 'def test_value():\n    text = \'assert actual == {"v": 3, "other": 4}\'\n    assert text\n'
    with pytest.raises(ValueError, match='exact_assertion'):
        run(payload)
