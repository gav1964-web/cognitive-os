"""A bounded excerpt must never replace or weaken whole-file patch identity."""
import hashlib

import pytest

from runtime.upstream_candidate_context import candidate_source_context
from runtime.upstream_llm_candidates import build_model_candidates, validate_model_candidate

PADDING = '# unrelated documentation\n' * 700


def test_large_module_keeps_transitive_dependencies_and_exact_file_hash():
    source = ('from fractions import Fraction as F\nLIMIT = 5\n'
        'def helper(x):\n    return F(x).limit_denominator(LIMIT)\n'
        'def target(x):\n    return helper(x)\n' + PADDING + 'def other():\n    return 42\n')
    r = candidate_source_context(source, 'module.py:target')
    assert len(r['source']) < 16000 and r['complete_module'] is False
    assert 'Fraction as F' in r['source'] and 'LIMIT = 5' in r['source']
    assert 'def helper' in r['source'] and 'def target' in r['source']
    assert 'def other' not in r['source'] and PADDING not in r['source']
    assert r['file_sha256'] == hashlib.sha256(source.encode()).hexdigest()


def test_full_file_edit_preserves_bytes_omitted_from_model_context():
    source = 'def target(x):\n    return x\n' + PADDING + 'OTHER = 42\n'
    packet = {'target': 'module.py:target', 'packet_digest': 'fixture-packet'}
    candidates = build_model_candidates({'candidates': [{'id': 'first',
        'replacement_source': 'def target(x):\n    return not x\n', 'reason': 'invert'}]},
        source=source, packet=packet, advisory={'model_response_digest': 'fixture-response'})
    candidate = candidates[0]
    assert candidate['replacement_source'].endswith(PADDING + 'OTHER = 42\n')
    validate_model_candidate(candidate, packet, source)
    changed = dict(candidate, replacement_source=candidate_source_context(source, packet['target'])['source'])
    with pytest.raises(ValueError, match='replacement_mismatch'):
        validate_model_candidate(changed, packet, source)


def test_large_referenced_value_is_not_silently_truncated():
    source = 'VALUE = ' + repr('x' * 17000) + '\ndef target():\n    return VALUE\n'
    with pytest.raises(ValueError, match='context_budget'):
        candidate_source_context(source, 'module.py:target')


def test_small_source_remains_complete():
    source = 'def target(x):\n    return x\n'
    r = candidate_source_context(source, 'module.py:target')
    assert r['source'] == source and r['complete_module'] is True


def test_file_budget_remains_bounded():
    with pytest.raises(ValueError, match='source_budget'):
        candidate_source_context('#' * 1_000_001, 'module.py:target')


def test_echoed_input_schema_is_rejected_without_silent_repair():
    with pytest.raises(ValueError, match='candidate_response_schema'):
        build_model_candidates({'schema_version': 'upstream_task_contract.v1', 'candidates': []},
            source='def target():\n    return 1\n', packet={'target': 'module.py:target'}, advisory={})


def test_large_module_cannot_choose_ambiguous_target():
    source = 'def target():\n    return 1\ndef target():\n    return 2\n' + PADDING
    with pytest.raises(ValueError, match='not_unique'):
        candidate_source_context(source, 'module.py:target')


def test_exact_model_delivery_from_large_module(tmp_path):
    from tests.runtime.test_model_candidate_delivery import _run_case, SOURCE
    project, result = _run_case(tmp_path, source=SOURCE + PADDING)
    assert result['status'] == 'experiment_validated'
    assert result['experiment']['final_review']['recommendation'] == 'approve'
    assert (project / 'logic.py').read_text(encoding='utf-8') == SOURCE + PADDING
