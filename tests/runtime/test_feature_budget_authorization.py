"""Extending a series needs an explicit grant and cannot discard earlier usage."""
import json

import pytest

from runtime.feature_inference import FeatureChat
from runtime.claim_suite_budget import _read
from tests.runtime.test_feature_inference import success, config


def test_grant_retains_usage_and_enforces_extended_ceiling(tmp_path):
    old = tmp_path / 'old.json'
    old.write_text(json.dumps({'schema_version': 'claim_suite_budget.v1',
        'limit_exclusive': 1000000, 'jobs': {'past': {'state': 'done',
            'reserved_tokens': 1100000, 'reported_tokens': 1100000}}}))
    grant = tmp_path / 'grant.json'
    grant.write_text(json.dumps({'schema_version': 'budget_authorization.v1',
        'authority': 'user', 'reason': 'explicit continuation authorization',
        'limit_exclusive': 1500000}))
    with pytest.raises(ValueError, match='authorization_required'):
        FeatureChat(tmp_path / 'no-grant', carry=old, budget_limit=1500000)
    with pytest.raises(ValueError, match='carried_ledger'):
        FeatureChat(tmp_path / 'no-carry', budget_limit=1500000, budget_authorization=grant)
    out = tmp_path / 'run'; out.mkdir()
    chat = FeatureChat(out, carry=old, budget_limit=1500000,
        budget_authorization=grant, transport=success)
    chat([], config=config())
    data = _read(chat.ledger)
    assert data['jobs']['past']['reported_tokens'] == 1100000
    assert data['limit_exclusive'] == 1500000
    data['jobs']['past']['reported_tokens'] = 1450000
    chat.ledger.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='next_call_budget'):
        chat([{'role': 'user', 'content': 'next'}], config=config())
    assert len(chat.attempts) == 1


def test_bare_ledger_limit_edit_is_not_a_grant(tmp_path):
    path = tmp_path / 'ledger.json'
    path.write_text(json.dumps({'schema_version': 'claim_suite_budget.v1',
        'limit_exclusive': 1500000, 'jobs': {}}))
    with pytest.raises(ValueError, match='authorization_required'):
        _read(path)


def test_new_series_is_explicit_and_cannot_overwrite_its_existing_ledger(tmp_path):
    grant = tmp_path / 'grant.json'
    grant.write_text(json.dumps({'schema_version': 'budget_authorization.v1',
        'authority': 'user', 'reason': 'new task, separately authorized budget',
        'limit_exclusive': 2000000}))
    out = tmp_path / 'new-series'
    chat = FeatureChat(out, budget_limit=2000000, budget_authorization=grant,
                       start_new_series=True, transport=success)
    chat([], config=config())
    original = chat.ledger.read_bytes()
    with pytest.raises(ValueError, match='fresh_uncarried_ledger'):
        FeatureChat(out, budget_limit=2000000, budget_authorization=grant, start_new_series=True)
    with pytest.raises(ValueError, match='fresh_uncarried_ledger'):
        FeatureChat(tmp_path / 'other', carry=chat.ledger, start_new_series=True)
    assert chat.ledger.read_bytes() == original
