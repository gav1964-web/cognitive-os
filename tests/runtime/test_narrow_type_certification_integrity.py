"""A recomputed JSON hash is not evidence of valid role scores."""
import copy
import hashlib
import json

import pytest

from runtime.narrow_type_certification import (
    build_narrow_type_certification, verify_narrow_type_certification,
)
from runtime.narrow_type_evidence_binding import content_digest
from runtime.role_project_type_evaluation_policy import load_role_project_type_policy
from tests.runtime.test_narrow_type_certification import _evaluation, _receipt


def _rehash(certificate):
    body = {key: value for key, value in certificate.items() if key != 'certificate_digest'}
    raw = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    certificate['certificate_digest'] = 'sha256:' + hashlib.sha256(raw).hexdigest()
    return certificate


@pytest.mark.parametrize('mutation', ['weak_score', 'missing_cell', 'duplicate_cell', 'lower_target'])
def test_rehashed_invalid_certificate_is_rejected(tmp_path, mutation):
    certificate = build_narrow_type_certification(
        evaluation=_evaluation(), evidence_root=tmp_path, holdout_receipt=_receipt(tmp_path),
    )
    assert verify_narrow_type_certification(certificate, evidence_root=tmp_path)
    if mutation == 'weak_score':
        certificate['cell_checks'][0]['score'] = 1.0
    elif mutation == 'missing_cell':
        certificate['cell_checks'].pop()
    elif mutation == 'duplicate_cell':
        certificate['cell_checks'][1] = copy.deepcopy(certificate['cell_checks'][0])
    else:
        certificate['target_score'] = 1.0
    assert not verify_narrow_type_certification(_rehash(certificate), evidence_root=tmp_path)


def test_rehashed_reference_to_failed_holdout_is_rejected(tmp_path):
    certificate = build_narrow_type_certification(
        evaluation=_evaluation(), evidence_root=tmp_path, holdout_receipt=_receipt(tmp_path),
    )
    certificate['receipt'] = _receipt(tmp_path, no_role_regression=False)
    assert not verify_narrow_type_certification(_rehash(certificate), evidence_root=tmp_path)


@pytest.mark.parametrize('score', [float('inf'), float('nan'), 10.1, True])
def test_invalid_numeric_score_is_not_certifiable(tmp_path, score):
    evaluation = _evaluation()
    evaluation['cells'][0]['score'] = score
    certificate = build_narrow_type_certification(
        evaluation=evaluation, evidence_root=tmp_path,
        holdout_receipt=_receipt(tmp_path, evaluation=evaluation),
    )
    assert certificate['status'] == 'evidence_required'
    assert certificate['cell_checks'][0]['checks']['measured'] is False


def test_duplicate_evaluation_cannot_hide_weak_role(tmp_path):
    evaluation = _evaluation()
    weak = {**evaluation['cells'][0], 'score': 1.0}
    evaluation['cells'].insert(0, weak)
    certificate = build_narrow_type_certification(
        evaluation=evaluation, evidence_root=tmp_path,
        holdout_receipt=_receipt(tmp_path, evaluation=evaluation),
    )
    assert certificate['status'] == 'evidence_required'
    assert certificate['cell_checks'][0]['checks']['unique_cell'] is False


def test_evaluation_must_be_the_one_reviewed_in_holdout(tmp_path):
    certificate = build_narrow_type_certification(
        evaluation=_evaluation(9.9), evidence_root=tmp_path, holdout_receipt=_receipt(tmp_path),
    )
    assert certificate['receipt_checks']['evaluation_content_bound'] is False
    assert certificate['status'] == 'evidence_required'


def test_certificate_is_not_authority_without_ledger_access(tmp_path):
    certificate = build_narrow_type_certification(
        evaluation=_evaluation(), evidence_root=tmp_path, holdout_receipt=_receipt(tmp_path),
    )
    assert verify_narrow_type_certification(certificate) is False


def test_substituted_passing_holdout_is_rejected(tmp_path):
    certificate = build_narrow_type_certification(
        evaluation=_evaluation(), evidence_root=tmp_path, holdout_receipt=_receipt(tmp_path),
    )
    certificate['receipt'] = _receipt(tmp_path, evaluation=_evaluation(9.9))
    assert not verify_narrow_type_certification(_rehash(certificate), evidence_root=tmp_path)


def test_rehashed_evaluation_cannot_reuse_prior_holdout(tmp_path):
    certificate = build_narrow_type_certification(
        evaluation=_evaluation(), evidence_root=tmp_path, holdout_receipt=_receipt(tmp_path),
    )
    certificate['evaluation'] = _evaluation(9.9)
    certificate['evaluation_digest'] = content_digest(certificate['evaluation'])
    for cell in certificate['cell_checks']:
        cell['score'] = 9.9
    assert not verify_narrow_type_certification(_rehash(certificate), evidence_root=tmp_path)


def test_policy_change_requires_reassessment(tmp_path):
    certificate = build_narrow_type_certification(
        evaluation=_evaluation(), evidence_root=tmp_path, holdout_receipt=_receipt(tmp_path),
    )
    policy = load_role_project_type_policy()
    policy['development_priority']['current_lane']['target_score'] = 9.9
    assert not verify_narrow_type_certification(certificate, evidence_root=tmp_path, policy=policy)


@pytest.mark.parametrize('malformed', [None, {}, {'status': 'certified', 'evaluation': {}}])
def test_malformed_certificate_fails_closed(tmp_path, malformed):
    assert not verify_narrow_type_certification(malformed, evidence_root=tmp_path)
