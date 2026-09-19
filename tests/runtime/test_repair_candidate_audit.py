"""Report structural facts without promoting them to semantic acceptance."""
import hashlib
from copy import deepcopy

import pytest

from runtime.narrow_type_evidence_binding import content_digest
from runtime.repair_candidate_audit import candidate_repair_audit
from runtime.upstream_llm_candidates import build_model_candidates, validate_model_candidate

SOURCE = "class Converter:\n    def convert(self, inline):\n        if inline:\n            return ''\n        return 'break'\n"
TARGET = 'core.py:Converter.convert'


def inputs():
    packet = {'target': TARGET, 'packet_digest': 'fixture',
              'target_source': {'file_sha256': hashlib.sha256(SOURCE.encode()).hexdigest()}}
    design = {'target': TARGET, 'branch_digest': 'source-bound-trace-fixture',
        'reached_return_ids': ['R1'], 'reached_returns': [{'id': 'R1', 'line': 4, 'source': "return ''"}],
        'mutation_contract': {'change': 'Change the reached return; retain the alternative branch.'}}
    return packet, design


@pytest.mark.parametrize('replacement,count', [
    ("def convert(self, inline):\n    if inline:\n        return ''\n    return 'different'\n", 1),
    ("def convert(self, inline):\n    if inline:\n        return ' '\n    return 'break'\n", 0),
    ("def convert(self, inline):\n    if not inline:\n        return ''\n    return 'break'\n", 1),
    ("def convert(self, inline):\n    def helper():\n        return ''\n    return 'break'\n", 0),
])
def test_return_occurrences_are_not_branch_or_behavior_claims(replacement, count):
    packet, design = inputs()
    audit = candidate_repair_audit(SOURCE, TARGET, replacement, design, packet)
    assert audit['reached_returns'][0]['equivalent_return_count_in_candidate'] == count
    assert audit['execution_authorized'] is False
    assert 'different guards' in audit['limitations']


@pytest.mark.parametrize('change', ['source', 'line', 'expression', 'ids'])
def test_source_and_grounding_must_match(change):
    packet, design = inputs()
    source = SOURCE
    if change == 'source': source += '# changed\n'
    if change == 'line': design['reached_returns'][0]['line'] = 5
    if change == 'expression': design['reached_returns'][0]['source'] = "return 'invented'"
    if change == 'ids': design['reached_return_ids'] = ['R2']
    with pytest.raises(ValueError):
        candidate_repair_audit(source, TARGET, 'def convert(self, inline):\n    return 1\n', design, packet)


def test_candidate_provenance_recomputes_audit_even_after_outer_digest_rehash():
    packet, design = inputs()
    advisory = {'repair_design': design, 'model_response_digest': 'scripted'}
    payload = {'candidates': [{'id': 'candidate', 'reason': 'scripted fixture',
        'replacement_source': "def convert(self, inline):\n    return 'break'\n"}]}
    candidate = build_model_candidates(payload, packet=packet, advisory=advisory, source=SOURCE)[0]
    validate_model_candidate(candidate, packet, SOURCE)
    changed = deepcopy(candidate)
    proof = changed['provenance']
    proof['repair_audit']['reached_returns'][0]['equivalent_return_count_in_candidate'] = 99
    proof['provenance_digest'] = content_digest({k: v for k, v in proof.items() if k != 'provenance_digest'})
    with pytest.raises(ValueError, match='repair_audit_mismatch'):
        validate_model_candidate(changed, packet, SOURCE)
