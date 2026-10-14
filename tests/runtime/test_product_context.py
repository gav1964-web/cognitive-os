from copy import deepcopy
import hashlib

import pytest

from runtime.architecture_decision_builder import build_architecture_decision
from runtime.technical_spec_builder import build_technical_spec
from runtime.upstream_role_handoff import frame_analysis
from runtime.product_context import make_product_context, checked_product_context
from runtime.role_pipeline import run_role_pipeline


@pytest.fixture
def product(tmp_path):
    source = tmp_path / 'core.py'
    source.write_text('def total(rows): return sum(rows)\n')
    claim = {'text': 'Totals supplied rows.', 'evidence_ids': ['s1']}
    report = {'status': 'described', 'description': {'purpose': claim, 'scenarios': [claim],
        'data_flow': [claim], 'unknowns': ['Required output format?'], 'confidence': 'medium'},
        'owner_notes': [], 'evidence': {'root': str(tmp_path), 'sources': [
            {'id': 's1', 'path': 'core.py', 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}]}}
    packet = make_product_context(report, accepted_claim_ids=['purpose', 'scenarios.0'],
                                  reviewer='assistant_source_review', constraints=['Retain input order.'])
    return tmp_path, packet, report


def test_reviewed_product_context_survives_actual_role_builders(product):
    root, context, _ = product
    contract = {'schema_version': 'upstream_task_contract.v1', 'origin': 'assistant_supplied',
        'change_kind': 'feature', 'requirements': [{'id': 'R1', 'statement': 'Keep empty total zero.',
            'targets': ['core.py:total'], 'acceptance_examples': [{'input': [], 'expected': 0}]}],
        'constraints': []}
    report = {'root': str(root), 'summary': {'root': str(root)}}
    analysis = frame_analysis(report, contract, context)
    architecture = build_architecture_decision(goal='Preserve totals', project_report=analysis)
    spec = build_technical_spec(architecture_decision=architecture)
    assert analysis['product_context'] == architecture['product_context'] == spec['product_context']
    assert spec['product_context']['unknowns'] == ['Required output format?']
    assert spec['product_context']['constraints'] == ['Retain input order.']
    assert not spec['product_context']['execution_authorized']
    assert spec['implementation_delta']['status'] == 'blocked'


@pytest.mark.parametrize('mutation', ['source', 'root', 'claim', 'authority'])
def test_stale_foreign_or_tampered_context_is_rejected(product, mutation, tmp_path):
    root, context, _ = product
    if mutation == 'source':
        (root / 'core.py').write_text('def total(rows): return -1\n')
    elif mutation == 'root':
        root = tmp_path / 'another'
    elif mutation == 'claim':
        context['claims'][0]['text'] = 'Unreviewed new purpose'
    else:
        context['execution_authorized'] = True
    with pytest.raises(ValueError):
        checked_product_context(context, root)


def test_explicit_claim_review_and_success_are_required(product):
    _, _, report = product
    with pytest.raises(ValueError):
        make_product_context(report, accepted_claim_ids=[], reviewer='assistant')
    report['status'] = 'failed'
    with pytest.raises(ValueError):
        make_product_context(report, accepted_claim_ids=['purpose'], reviewer='assistant')


def test_product_context_does_not_enable_executor(product):
    root, context, _ = product
    with pytest.raises(ValueError, match='design_validation'):
        run_role_pipeline(root=root, project_dir=root, goal='Change', product_context=context, run_executor=True)


def test_context_does_not_mutate_input_and_requires_current_sources_at_architect(product):
    root, context, _ = product
    original = deepcopy(context)
    analysis = frame_analysis({'root': str(root), 'summary': {'root': str(root)}}, None, context)
    assert context == original
    (root / 'core.py').write_text('def total(rows): return 99\n')
    with pytest.raises(ValueError, match='stale_sources'):
        build_architecture_decision(goal='Change', project_report=analysis)
