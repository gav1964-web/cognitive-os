"""Source selection/lookup regressions; facts are not project-specific rules."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from plugins.project_description.src.claim_evidence import review_context
from plugins.project_description.src.helper_context import sections, helper_order, select_context
from plugins.project_description.src.source_lookup import read_requests

ROOT = Path(__file__).resolve().parents[2]


def policy():
    return json.loads((ROOT / 'plugins/project_description/knowledge/description_policy.json').read_text(encoding='utf-8'))


def lookup(tmp_path, text, name='dispatch'):
    path = tmp_path / 'worker.py'
    path.write_bytes(text.encode())
    request = {'path': 'worker.py', 'symbol': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    return read_requests(tmp_path, [request], policy()['collection'])[0]


def test_same_file_lookup_includes_transitive_helpers_without_execution(tmp_path):
    text = 'raise RuntimeError("never execute")\ndef dispatch(x):\n    return middle(x)\ndef middle(x):\n    return leaf(x)\ndef leaf(x):\n    return "VISIBLE_LEAF"\n'
    result = lookup(tmp_path, text)
    assert 'VISIBLE_LEAF' in result['excerpt']
    assert [r['symbol'] for r in result['helper_context']['ranges']] == ['dispatch', 'middle', 'leaf']
    assert not result['truncated']
    assert 'not_runtime_binding' in result['helper_context']['authority']


@pytest.mark.parametrize('caller', [
    'def dispatch(helper):\n    return helper()\n',
    'def dispatch():\n    helper = lambda: 2\n    return helper()\n',
    'def dispatch():\n    from elsewhere import helper\n    return helper()\n',
    'def dispatch():\n    def nested():\n        return helper()\n    return nested()\n',
])
def test_shadowed_imported_and_nested_calls_are_not_module_helper_edges(caller):
    text = caller + 'def helper():\n    return "WRONG_TARGET"\n'
    assert helper_order(sections(text), ['dispatch']) == []


def test_cycle_and_duplicate_names_do_not_expand_forever(tmp_path):
    cyclic = lookup(tmp_path, 'def dispatch():\n    return helper()\ndef helper():\n    return dispatch()\n')
    assert len(cyclic['helper_context']['ranges']) == 2
    duplicate = 'def dispatch():\n    return helper()\ndef helper():\n    return 1\ndef helper():\n    return 2\n'
    assert helper_order(sections(duplicate), ['dispatch']) == []


def test_expansion_is_bounded_redacted_and_reports_omitted_helpers(tmp_path):
    source = 'def dispatch():\n' + ''.join(f'    step_{n}()\n' for n in range(12))
    source += ''.join(f'def step_{n}():\n    password = "SECRET_{n}"\n    return password\n' for n in range(12))
    result = lookup(tmp_path, source)
    assert len(result['excerpt']) <= 10000 and 'SECRET_' not in result['excerpt']
    assert len(result['helper_context']['ranges']) == 7
    assert result['truncated'] and result['helper_context']['omitted_helper_count'] == 6


def test_oversized_caller_stays_explicitly_truncated(tmp_path):
    source = 'def dispatch():\n' + '    value = "' + 'x' * 11000 + '"\n'
    result = lookup(tmp_path, source)
    assert len(result['excerpt']) <= 10000 and result['truncated']
    assert result['helper_context']['caller_truncated']


def test_large_secret_is_redacted_before_expansion_truncates_it(tmp_path):
    source = 'def dispatch():\n    api_key = "' + 'PRIVATE_CANARY' * 1200 + '"\n    return api_key\n'
    result = lookup(tmp_path, source)
    assert 'PRIVATE_CANARY' not in json.dumps(result)
    assert '[REDACTED]' in result['excerpt']


def test_expanded_lookup_survives_review_budget(tmp_path):
    result = lookup(tmp_path, 'def dispatch(x):\n    return classify(x)\ndef classify(x):\n    if x:\n        return "BRANCH_A"\n    return "BRANCH_B"\n')
    evidence = {'root': str(tmp_path), 'sources': [result]}
    claims = [{'id': 'purpose', 'text': 'Calls `dispatch`.', 'evidence_ids': ['x1']}]
    view = review_context(evidence, claims, policy()['claim_review'])
    assert 'BRANCH_A' in view['evidence']['sources'][0]['excerpt']
    assert 'BRANCH_B' in view['evidence']['sources'][0]['excerpt']


def test_saved_context_retains_available_predicates_and_purpose_without_extra_reads():
    fixture = json.loads((ROOT / 'tests/fixtures/project_description/helper_context_failure.json').read_text(encoding='utf-8'))
    before = deepcopy(fixture)
    result = review_context(fixture['evidence'], fixture['claims'], policy()['claim_review'])
    sources = result['evidence']['sources']
    stack = next(s for s in sources if s['path'].endswith('/stack.py'))
    commands = next(s for s in sources if s['path'].endswith('/commands.py'))
    assert 'def _frameworks(' in stack['excerpt'] and '"fastapi" in dependency_text' in stack['excerpt']
    assert '[... omitted ...]' in stack['excerpt']  # Already abbreviated input is never called complete.
    assert 'return "install_dependencies"' in commands['excerpt']
    assert fixture == before and result['context_characters'] <= 32000


def test_section_selection_is_bounded_for_small_budgets():
    text = 'def dispatch(x):\n    return helper(x)\ndef helper(x):\n    return x\n' + '# filler\n' * 1000
    for budget in (0, 10, 100, 500, 1400):
        result = select_context(text, budget)
        assert result is None or len(result) <= budget
