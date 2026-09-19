"""The frozen protocol must not leak expected answers or call models."""
import json

import pytest

from tools.prepare_claim_obligation_suite import prepare_suite, DEFAULT_CASES
from runtime.single_claim_review import checked_job, review_messages
from runtime.narrow_type_evidence_binding import content_digest


def test_freeze_jobs_without_sending_expectations(tmp_path, monkeypatch):
    import runtime.single_claim_review as review
    monkeypatch.setattr(review, 'call_json_chat', lambda *a, **k: pytest.fail('Offline preparation'))
    output = tmp_path / 'suite'
    protocol = prepare_suite(DEFAULT_CASES, output)
    assert protocol['model_calls'] == 0 and len(protocol['cases']) == 5
    for case in protocol['cases']:
        job = json.loads((output / case['job']).read_text(encoding='utf-8'))
        checked_job(job)
        assert job['digest'] == case['job_digest']
        messages = review_messages(job)
        assert content_digest(messages) == case['messages_digest']
        content = messages[1]['content']
        assert 'expected_verdict' not in content and case['rationale'] not in content
    with pytest.raises(FileExistsError):
        prepare_suite(DEFAULT_CASES, output)
