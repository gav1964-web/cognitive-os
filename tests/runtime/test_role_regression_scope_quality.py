"""Historical green checks alone cannot certify an unchanged test contract."""
import pytest
from runtime.narrow_type_role_semantics import evaluate_narrow_type_role_semantics
from tests.runtime.test_narrow_type_role_semantics import _cases, ROLES


@pytest.mark.parametrize('mode',['missing','removed','tampered'])
def test_missing_or_invalid_regression_scope_caps_role_claim(monkeypatch,mode):
    monkeypatch.setattr('runtime.narrow_type_role_semantics.evaluate_foundation_semantic_quality',
        lambda *_a,**_k:{'role_scores':{role:10.0 for role in ROLES}})
    cases=_cases()
    native=cases[0]['execution_run']['experiment']['project_native_verification']
    if mode=='missing':native.pop('regression_scope')
    elif mode=='removed':native['regression_scope']['checks']['original_tests_retained']=False
    else:native['regression_scope']['candidate_inventory_digest']='forged'
    report=evaluate_narrow_type_role_semantics(cases=cases,evaluation_split='holdout',target_score=9.0)
    assert report['schema_version']=='narrow_type_role_semantic_evidence.v3'
    assert report['status']=='evidence_required'
    assert report['role_scores']['spec_writer']<9.0
    assert 'regression_contract_preserved' in report['cases'][0]['failed_checks']['tester']
