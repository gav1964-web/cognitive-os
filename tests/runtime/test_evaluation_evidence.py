"""Counterexamples from the September audit, exercised against actual files."""
import copy
import hashlib
import json

import pytest

from runtime.evaluation_evidence import artifact_bytes
from runtime.evaluation_protocol_policy import numeric_policy_errors
from runtime.three_route_evaluation import build_blind_bundle, freeze_manifest, protocol_status, validate_receipt
from runtime.three_route_evaluation_scoring import score_blind_evaluation
from tests.runtime.test_three_route_evaluation import POLICY, ROUTES, _task, _receipt


@pytest.fixture
def campaign(tmp_path):
    _task(tmp_path)
    manifest = freeze_manifest(tmp_path, source_commit='test')
    return tmp_path, manifest, [copy.deepcopy(_receipt(manifest, r)) for r in ROUTES]


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -float('inf'), -1, True, 10**400])
@pytest.mark.parametrize('field', ['runtime_seconds', 'estimated_cost', 'minutes'])
def test_invalid_metrics_are_rejected(campaign, field, value):
    root, manifest, receipts = campaign
    receipt = receipts[0]
    if field == 'minutes':
        receipt['manual_corrections'] = [{'kind': 'edit', 'minutes': value}]
        expected = 'invalid_manual_correction'
    else:
        receipt[field] = value
        expected = 'invalid_' + field
    assert expected in validate_receipt(receipt, manifest, POLICY, artifact_root=root)
    with pytest.raises(ValueError):
        build_blind_bundle(manifest, receipts, POLICY, artifact_root=root)


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -1, True, '0.3'])
def test_invalid_policy_numbers_are_rejected(value):
    policy = copy.deepcopy(POLICY)
    policy['rubric']['correctness'] = value
    assert 'invalid_rubric_weights' in numeric_policy_errors(policy)
    policy = copy.deepcopy(POLICY)
    policy['winner_margin'] = value
    assert 'invalid_winner_margin' in numeric_policy_errors(policy)


@pytest.mark.parametrize('mode', ['missing', 'changed', 'no_root', 'duplicate'])
def test_bundle_requires_actual_artifacts(campaign, mode):
    root, manifest, receipts = campaign
    if mode == 'missing':
        (root / 'result.txt').unlink()
    elif mode == 'changed':
        (root / 'result.txt').write_text('different')
    elif mode == 'duplicate':
        receipts[0]['artifacts'].append(receipts[0]['artifacts'][0])
    with pytest.raises(ValueError, match='artifact'):
        build_blind_bundle(manifest, receipts, POLICY, artifact_root=None if mode == 'no_root' else root)


@pytest.mark.parametrize('name', ['../outside', '/absolute', 'C:/outside', 'x:stream',
                                 'config.json', 'sub/.env.local', '.codex/settings', 'sub\\a'])
def test_artifact_paths_rejected_before_read(tmp_path, name):
    with pytest.raises(ValueError, match='artifact_path'):
        artifact_bytes(tmp_path, name)


def test_symlink_artifact_rejected(tmp_path):
    target = tmp_path / 'target'
    target.write_text('data')
    try:
        (tmp_path / 'link').symlink_to(target)
    except OSError:
        pytest.skip('symlink privilege unavailable')
    with pytest.raises(ValueError, match='artifact_link'):
        artifact_bytes(tmp_path, 'link')


def test_trace_must_match_and_mixed_models_reject_same_model_comparison(campaign):
    root, manifest, receipts = campaign
    receipts[0]['llm_attempts'].append({
        'model': 'GigaChat-Pro', 'requested_model': 'GigaChat-Pro',
        'provider_label': 'gateway', 'model_reported': True,
    })
    errors = validate_receipt(receipts[0], manifest, POLICY, artifact_root=root)
    assert 'actual_model_mismatch' in errors
    assert 'llm_trace_history_mismatch' in errors
    with pytest.raises(ValueError, match='actual_model_mismatch'):
        build_blind_bundle(manifest, receipts, POLICY, artifact_root=root)


def test_unknown_actual_model_is_not_inferred_from_config(campaign):
    root, manifest, receipts = campaign
    receipts[0]['llm_attempts'][0]['model_reported'] = False
    assert 'actual_model_unverified' in validate_receipt(receipts[0], manifest, POLICY, artifact_root=root)


def test_gateway_without_model_does_not_emit_verified_identity():
    from runtime.local_inference import LocalInferenceConfig, _emit_telemetry
    records = []
    cfg = LocalInferenceConfig('http://gateway/v1', 'configured-model', telemetry_sink=records.append)
    _emit_telemetry(cfg, {}, 0.1)
    assert records[0]['requested_model'] == 'configured-model'
    assert records[0]['model_reported'] is False
    _emit_telemetry(cfg, {'model': 'reported-model'}, 0.1)
    assert records[1]['model'] == 'reported-model'
    assert records[1]['model_reported'] is True


def test_quota_failure_then_single_backup_model_can_be_compared(campaign):
    root, manifest, receipts = campaign
    for row in receipts:
        row['llm_attempts'].insert(0, {'event': 'attempt_failed', 'requested_model': 'primary',
                                       'provider_label': 'gateway', 'http_status': 429})
    raw = json.dumps(receipts[0]['llm_attempts']).encode()
    (root / 'trace.json').write_bytes(raw)
    for row in receipts:
        row['artifacts'][1]['digest'] = 'sha256:' + hashlib.sha256(raw).hexdigest()
    build_blind_bundle(manifest, receipts, POLICY, artifact_root=root)


def scorecard(bundle):
    return {
        'bundle_digest': bundle['bundle_digest'],
        'judge': {'id': 'test', 'independent': True, 'produced_route_output': False,
                  'saw_blind_key_before_scoring': False},
        'scores': [{'task_id': c['task_id'], 'candidate_id': c['candidate_id'],
                    'rubric': {k: 8 for k in POLICY['rubric']}} for c in bundle['candidates']],
    }


@pytest.mark.parametrize('mutation', ['receipt', 'file', 'missing_receipt', 'duplicate', 'policy', 'boolean_score'])
def test_scoring_rechecks_bound_evidence(campaign, mutation):
    root, manifest, receipts = campaign
    bundle, key = build_blind_bundle(manifest, receipts, POLICY, artifact_root=root)
    policy = copy.deepcopy(POLICY)
    card = scorecard(bundle)
    if mutation == 'receipt':
        receipts[0]['estimated_cost'] = 900
    elif mutation == 'file':
        (root / 'result.txt').write_text('tampered')
    elif mutation == 'missing_receipt':
        receipts.pop()
    elif mutation == 'duplicate':
        receipts.append(receipts[0])
    elif mutation == 'policy':
        policy['winner_margin'] = 2
    else:
        card['scores'][0]['rubric']['correctness'] = True
    with pytest.raises(ValueError):
        score_blind_evaluation(bundle=bundle, blind_key=key, scorecard=card,
                               receipts=receipts, policy=policy, artifact_root=root)


def test_status_does_not_accept_duplicate_or_model_mismatched_triples(campaign):
    root, manifest, receipts = campaign
    receipts.append(receipts[0])
    status = protocol_status(manifest, receipts, POLICY, artifact_root=root)
    assert status['claim_eligible'] is False
    assert status['status'] == 'evidence_required'
