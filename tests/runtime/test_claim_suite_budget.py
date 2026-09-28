"""Budget reservations fail closed on missing usage and never repeat calls."""
import json

import pytest

from runtime import claim_suite_budget as budget


@pytest.fixture
def slots(tmp_path, monkeypatch):
    monkeypatch.setattr(budget, 'estimate_reservation', lambda job: 100_000)
    jobs = [{'digest': 'first'}, {'digest': 'second'}]
    path = tmp_path / 'budget.json'
    budget.create_budget(path, jobs)
    return path, jobs


def test_conservative_total_must_be_strictly_below_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(budget, 'estimate_reservation', lambda job: 500_000)
    with pytest.raises(ValueError, match='not_below_million'):
        budget.create_budget(tmp_path / 'budget.json', [{'digest': 'a'}, {'digest': 'b'}])


def test_started_and_unknown_usage_block_future_calls(slots):
    path, jobs = slots
    budget.start_call(path, jobs[0])
    with pytest.raises(ValueError, match='unresolved_usage'):
        budget.start_call(path, jobs[1])
    assert not budget.settle_call(path, jobs[0], [])
    with pytest.raises(ValueError, match='unresolved_usage'):
        budget.check_budget(path, [jobs[1]])


def test_known_usage_does_not_authorize_a_repeat(slots):
    path, jobs = slots
    budget.start_call(path, jobs[0])
    assert budget.settle_call(path, jobs[0], [{'usage_reported': True, 'total_tokens': 800}])
    with pytest.raises(ValueError, match='already_started'):
        budget.start_call(path, jobs[0])
    budget.start_call(path, jobs[1])
    budget.settle_call(path, jobs[1], [{'usage_reported': True, 'total_tokens': 900}])
    data = json.loads(path.read_text())
    assert sum(r['reported_tokens'] for r in data['jobs'].values()) == 1700


def test_usage_above_reservation_stops_before_next_request(slots):
    path, jobs = slots
    budget.start_call(path, jobs[0])
    budget.settle_call(path, jobs[0], [{'usage_reported': True, 'total_tokens': 900_000}])
    with pytest.raises(ValueError, match='not_below_million'):
        budget.start_call(path, jobs[1])


def test_invalid_reservation_cannot_disable_limit(slots):
    path, jobs = slots
    data = json.loads(path.read_text())
    data['jobs']['first']['reserved_tokens'] = -1
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='invalid_claim_suite_budget'):
        budget.check_budget(path, jobs)


def test_gateway_zero_placeholder_keeps_full_reservation_unknown(slots):
    path, jobs = slots
    budget.start_call(path, jobs[0])
    assert not budget.settle_call(path, jobs[0], [{
        'usage_reported': True, 'prompt_tokens': 0, 'completion_tokens': 0,
        'total_tokens': 0, 'gateway_route': {'cache_hit': False}}])
    row = json.loads(path.read_text())['jobs']['first']
    assert row == {'state':'unknown', 'reported_tokens':None, 'reserved_tokens':100_000}
    with pytest.raises(ValueError, match='unresolved_usage'):
        budget.start_call(path, jobs[1])


def test_explicit_unknown_policy_retains_reserve_and_blocks_inflight(slots):
    path, jobs = slots
    budget.start_call(path, jobs[0])
    with pytest.raises(ValueError, match='unresolved_usage'):
        budget.start_call(path, jobs[1], allow_unknown_reservations=True)
    budget.settle_call(path, jobs[0], [])
    budget.start_call(path, jobs[1], allow_unknown_reservations=True)
    row = json.loads(path.read_text())['jobs']['first']
    assert row['state'] == 'unknown' and row['reported_tokens'] is None
    assert row['reserved_tokens'] == 100_000


def test_unknown_policy_does_not_bypass_package_ceiling(slots):
    path, jobs = slots
    budget.start_call(path, jobs[0])
    budget.settle_call(path, jobs[0], [])
    data = json.loads(path.read_text())
    data['jobs']['first']['reserved_tokens'] = 900_000
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='not_below_million'):
        budget.start_call(path, jobs[1], allow_unknown_reservations=True)
