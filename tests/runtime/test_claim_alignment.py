"""Boundary normalization must preserve every word and historical contracts."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from plugins.project_description.src.claim_alignment import align_parts
from runtime.single_claim_review import prepare_claim_review, run_claim_review
from runtime.claim_review_proposals import checked_proposal
from runtime.claim_review_reporting import inspect_review, render_review
from runtime.narrow_type_evidence_binding import content_digest
from tests.runtime.test_lean_claim_review import saved_report


@pytest.mark.parametrize('original,parts', [
    ('One, and two.', ['One,', 'and two.']),
    ('One, and two.', ['One,  ', ' and two.']),
    ('A.\r\nB.', ['A.', 'B.']),
    ('one two three', ['one', 'two', 'three']),
    ('one one', ['one', 'one']),
])
def test_only_boundary_space_is_recovered_with_trace(original, parts):
    raw = [{'text': p} for p in parts]
    before = deepcopy(raw)
    normalized, audit = align_parts(raw, original)
    assert ''.join(p['text'] for p in normalized) == original
    assert raw == before and audit['status'] == 'boundary_whitespace_aligned'
    assert audit['changes'] and not audit['word_changes_allowed']
    for part, span in zip(normalized, audit['spans']):
        assert original[span['start']:span['end']] == part['text']


@pytest.mark.parametrize('original,parts', [
    ('Does not write.', ['Does ', 'write.']),
    ('Only when ready, write.', ['write.']),
    ('One, and two.', ['One', 'and two.']),
    ('a b c', ['a c']),
    ('one one', ['one']),
    ('A. B.', ['B.', 'A.']),
    ('100 files', ['1 ', '00 files']),
    ('cannot write', ['can ', 'not write']),
    ('some thing', ['something']),
    ('a\u00a0b', ['a', 'b']),
])
def test_words_punctuation_order_and_internal_space_cannot_be_repaired(original, parts):
    with pytest.raises(ValueError):
        align_parts([{'text': p} for p in parts], original)


def test_historical_v3_still_fails_while_new_v4_records_alignment(tmp_path):
    folder = Path(__file__).resolve().parents[1] / 'fixtures/project_description'
    fixture = json.loads((folder / 'v3_boundary_failure.json').read_text(encoding='utf-8'))
    report = saved_report(tmp_path, fixture['source'], fixture['claim'])
    raw = fixture['response']
    before = deepcopy(raw)
    v3 = run_claim_review(prepare_claim_review(report, 'scenarios.0', review_version=3), chat=lambda *a, **k: raw)
    v4 = run_claim_review(prepare_claim_review(report, 'scenarios.0'), chat=lambda *a, **k: raw)
    assert v3['status'] == 'failed' and v4['status'] == 'reviewed'
    assert v4['job']['schema_version'].endswith('.v4') and v4['result']['verdict'] == 'refuted'
    assert v4['raw_response'] == before == raw
    checked_proposal(v4)
    assert 'Пробелы на границах частей восстановлены' in render_review(inspect_review(v4))
    v4['text_alignment']['changes'] = []
    v4['digest'] = content_digest({k: v for k, v in v4.items() if k != 'digest'})
    with pytest.raises(ValueError, match='result_changed'):
        checked_proposal(v4)


def test_exact_parts_do_not_lose_their_original_boundaries():
    parts = [{'text': 'a '}, {'text': 'b'}]
    normalized, audit = align_parts(parts, 'a b')
    assert normalized == parts and audit['status'] == 'exact' and not audit['changes']
