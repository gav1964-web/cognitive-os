"""All source assertions are obligations, including unreached later assertions."""
import hashlib
from copy import deepcopy

import pytest

from runtime.repair_assertion_contract import build_assertion_contract, validate_assertion_plan, validate_assertion_design
from runtime.project_development_llm_hypothesis import _validate_payload, _messages
from tests.runtime.test_repair_grounding_feedback import hypothesis


def packet(excerpt=None):
    excerpt = excerpt or "def test_examples():\n    assert convert('heading') == 'a b'\n    assert convert('table') == ' a b |'"
    return {'packet_digest': 'fixture', 'target': 'core.py:convert', 'failure_signature': 'fixture-failure',
        'test_sources': [{'path': 'tests/test_core.py', 'nodeid': 'tests/test_core.py::test_examples',
            'file_sha256': 'fixture-source-file', 'sha256': hashlib.sha256(excerpt.encode()).hexdigest(),
            'excerpt_complete': True, 'excerpt': excerpt}]}


def test_catalog_covers_all_assertions_without_claiming_execution():
    contract = build_assertion_contract(packet())
    assert [r['id'] for r in contract['assertions']] == ['A001', 'A002']
    assert 'table' in contract['assertions'][1]['assertion']
    assert contract['execution_authorized'] is False
    assert 'not inferred' in contract['scope']
    from runtime.repair_assertion_contract import assertion_prompt_context
    context = assertion_prompt_context(contract)
    assert context['contract_digest'] == contract['contract_digest']
    assert [r['assertion'] for r in context['assertions']] == [r['assertion'] for r in contract['assertions']]
    assert 'file_sha256' in contract['assertions'][0] and 'file_sha256' not in context['assertions'][0]


@pytest.mark.parametrize('change', ['truncated', 'hash', 'conditional', 'nested', 'none', 'budget'])
def test_incomplete_or_unsupported_assertion_scope_is_rejected(change):
    p = packet()
    if change == 'truncated': p['test_sources'][0]['excerpt_complete'] = False
    if change == 'hash': p['test_sources'][0]['excerpt'] += '\n    assert False'
    if change == 'conditional': p = packet('def test_x():\n    if enabled:\n        assert value == 1')
    if change == 'nested': p = packet('def test_x():\n    def helper():\n        assert value == 1\n    assert True')
    if change == 'none': p = packet('def test_x():\n    check(value)')
    if change == 'budget': p = packet('def test_x():\n' + '    assert True\n' * 65)
    with pytest.raises(ValueError): build_assertion_contract(p)


@pytest.mark.parametrize('change', ['none', 'missing', 'duplicate', 'unknown', 'empty', 'extra'])
def test_hypothesis_must_explain_each_assertion_exactly_once(change):
    p = packet(); contract = build_assertion_contract(p)
    plan = [{'assertion_id': r['id'], 'behavior': 'Preserve the exact asserted whitespace for this context.'}
            for r in contract['assertions']]
    if change == 'missing': plan.pop()
    if change == 'duplicate': plan[1]['assertion_id'] = plan[0]['assertion_id']
    if change == 'unknown': plan[0]['assertion_id'] = 'A999'
    if change == 'empty': plan[0]['behavior'] = ''
    if change == 'extra': plan[0]['passed'] = True
    envelope = {**p, 'assertion_contract': contract}
    _, errors = _validate_payload({**hypothesis(p), 'assertion_plan': plan}, envelope)
    assert ('complete_assertion_plan_required' in errors) == (change != 'none')
    assert 'assertion_plan' in _messages(envelope)[0]['content']


def test_resealed_contract_cannot_remove_a_later_assertion():
    from runtime.narrow_type_evidence_binding import content_digest
    p = packet(); contract = build_assertion_contract(p)
    changed = deepcopy(contract); changed['assertions'].pop()
    changed['contract_digest'] = content_digest({k:v for k,v in changed.items() if k!='contract_digest'})
    with pytest.raises(ValueError, match='contract_changed'):
        validate_assertion_design(p, {'assertion_contract': changed, 'assertion_plan': []})


def test_saved_feedback_cannot_enter_unauthorized_core(tmp_path):
    from runtime.project_development import run_project_development
    with pytest.raises(ValueError, match='counterexample_requires'):
        run_project_development(root=tmp_path, project_dir=tmp_path, goal='repair', repair_counterexample_comparison={})


def test_long_native_log_is_explicit_exact_suffix_with_full_identity():
    from runtime.repair_counterexamples import feedback_output
    from runtime.narrow_type_evidence_binding import content_digest
    output = 'long traceback\n' * 600 + "TypeError: 'set' object is not subscriptable\n1 failed\n"
    evidence = feedback_output(output)
    segment = evidence['output_excerpt']
    assert evidence['native_output'] == output[segment['start_char']:segment['end_char']]
    assert len(evidence['native_output']) == 2000
    assert segment['full_output_digest'] == content_digest(output)
    assert segment['omitted_prefix'] is True
    short = feedback_output('1 failed\n')
    assert short['native_output'] == '1 failed\n' and 'output_excerpt' not in short
