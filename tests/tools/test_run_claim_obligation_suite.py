"""Budget and crash behavior; test responses never call an inference provider."""
import json

import pytest

from runtime.local_inference import LocalInferenceError
from tools.prepare_claim_obligation_suite import prepare_suite, DEFAULT_CASES
from tools.run_claim_obligation_suite import run_suite, preflight


@pytest.fixture
def prepared(tmp_path):
    folder = tmp_path / 'frozen'
    prepare_suite(DEFAULT_CASES, folder, review_version=2)
    return folder / 'protocol.json', tmp_path / 'results'


def test_five_validation_failures_use_five_calls_without_expected_answers(prepared):
    protocol, output = prepared
    calls = []
    def chat(messages, *, config):
        calls.append(messages)
        assert config.timeout_seconds == 240 and not config.fallbacks
        assert config.max_output_tokens == 3200
        assert 'expected_verdict' not in messages[1]['content']
        return {}  # Invalid response is retained, never repaired by another call.
    state = run_suite(protocol, output, budget_reference='test only', chat=chat)
    assert len(calls) == 5 and state['status'] == 'completed' and state['budget_closed']
    assert all(r['status'] == 'failed' for r in state['attempts'])
    assert all(not r['usage_known'] for r in state['attempts'])
    assert json.loads((output / 'case05_result.json').read_text())['raw_response'] == {}
    with pytest.raises(FileExistsError):
        run_suite(protocol, output.parent / 'different', budget_reference='test', chat=chat)
    assert len(calls) == 5


@pytest.mark.parametrize('exception', [LocalInferenceError('local inference request failed: timeout'), RuntimeError('unexpected')])
def test_failure_stops_without_resuming_or_claiming_zero_usage(prepared, exception):
    protocol, output = prepared
    calls = []
    def chat(*args, **kwargs):
        calls.append(1)
        raise exception
    state = run_suite(protocol, output, budget_reference='test only', chat=chat)
    assert state['status'] == 'stopped' and len(calls) == 1 and state['budget_closed']
    assert not state['attempts'][0]['usage_known']
    with pytest.raises(ValueError, match='output_already_exists'):
        run_suite(protocol, output, budget_reference='test', chat=chat)


def test_all_inputs_are_checked_before_any_attempt(prepared):
    protocol, output = prepared
    (protocol.parent / 'case05/example.py').write_text('changed')
    with pytest.raises(ValueError, match='stale_sources'):
        run_suite(protocol, output, budget_reference='test',
                  chat=lambda *a, **k: pytest.fail('No call with a stale later input'))
    assert not output.exists() and not protocol.with_name('execution.json').exists()


def test_frozen_messages_and_job_paths_cannot_change(prepared):
    protocol, _ = prepared
    data = json.loads(protocol.read_text(encoding='utf-8'))
    data['cases'][0]['messages_digest'] = 'changed'
    protocol.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError, match='frozen_input_changed'):
        preflight(protocol)
    data['cases'][0]['job'] = '../outside.json'
    protocol.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError, match='outside_protocol'):
        preflight(protocol)


@pytest.mark.parametrize('usage_known', [True, False])
def test_v3_shared_budget_accounts_usage_and_stops_unknown(tmp_path, usage_known):
    from runtime.claim_suite_budget import create_budget, check_budget
    suites = []
    jobs = []
    for name in ('first', 'second'):
        folder = tmp_path / name
        prepare_suite(DEFAULT_CASES, folder)
        protocol = folder / 'protocol.json'
        jobs.extend(job for _, job in preflight(protocol)[1])
        suites.append(protocol)
    ledger = tmp_path / 'budget.json'
    create_budget(ledger, jobs)
    calls = []
    def chat(messages, *, config):
        calls.append(messages)
        if usage_known:
            config.telemetry_sink({'usage_reported': True, 'total_tokens': 1200})
        return {}
    result = run_suite(suites[0], tmp_path / 'out1', budget_reference='injected test',
                       token_budget=ledger, chat=chat)
    if usage_known:
        assert result['status'] == 'completed'
        run_suite(suites[1], tmp_path / 'out2', budget_reference='injected test',
                  token_budget=ledger, chat=chat)
        data = json.loads(ledger.read_text())
        assert len(calls) == 10
        assert sum(row['reported_tokens'] for row in data['jobs'].values()) == 12000
    else:
        assert result['status'] == 'stopped' and len(calls) == 1
        with pytest.raises(ValueError, match='budget_unresolved_usage'):
            check_budget(ledger, jobs[5:])


def test_v3_requires_budget_before_inference(tmp_path):
    folder = tmp_path / 'suite'
    prepare_suite(DEFAULT_CASES, folder)
    with pytest.raises(ValueError, match='suite_token_budget_required'):
        run_suite(folder / 'protocol.json', tmp_path / 'out', budget_reference='test',
                  chat=lambda *a, **k: pytest.fail('Budget required before inference'))
    assert not (folder / 'execution.json').exists()
