"""Previously qualified forecasts may be reused, never inferred or waived."""
from copy import deepcopy
import json

import pytest

from runtime.feature_accepted_metadata import capture, restore


def accepted():
    spec = {'tests': [{'path': 'tests/test_old.py', 'content': 'def test_old():\n    assert f(0) == 0\n'}],
        'baseline_expectations': [{'node': 'tests/test_old.py::test_old',
            'classification': 'preservation', 'reason': 'keep zero', 'goal_quote': 'zero',
            'source_evidence': [{'path': 'engine.py', 'quote': 'return value'}]}]}
    return spec, capture(spec, goal='preserve zero', design={'scope': ['engine.py']},
                         source_hashes={'engine.py': 'bound'})


@pytest.mark.parametrize('omit', [False, True])
def test_restore_only_exact_qualified_rows_with_receipt_and_immutable_bytes(omit):
    spec, saved = accepted()
    draft = deepcopy(spec)
    draft['baseline_expectations'] = [] if omit else [{**spec['baseline_expectations'][0],
        'goal_quote': 'preserve ... zero', 'classification': 'feature_gap'}]
    new = {'node': 'tests/test_extra.py::test_new', 'classification': 'feature_gap'}
    draft['tests'].append({'path': 'tests/test_extra.py', 'content': 'def test_new():\n    assert f(1) == 2\n'})
    draft['baseline_expectations'].append(new)
    before = deepcopy(draft)
    result, changes = restore(draft, saved, saved['binding'])
    assert draft == before and result['tests'] == before['tests']
    assert spec['baseline_expectations'][0] in result['baseline_expectations']
    assert new in result['baseline_expectations'] and len(changes) == 1
    assert changes[0]['grants_approval'] is False


@pytest.mark.parametrize('mutation', ['goal', 'design', 'source', 'test', 'missing', 'duplicate'])
def test_changed_bindings_or_ambiguous_tests_never_get_old_predictions(mutation):
    spec, saved = accepted()
    draft = deepcopy(spec)
    draft['baseline_expectations'] = []
    binding = saved['binding']
    if mutation in ('goal', 'design', 'source'):
        fields = {'goal': 'goal', 'design': 'dependency', 'source': 'source_inventory_digest'}
        payload = json.loads(binding); payload[fields[mutation]] = 'changed'
        binding = json.dumps(payload, sort_keys=True)
    elif mutation == 'test':
        draft['tests'][0]['content'] += '# changed\n'
    elif mutation == 'missing':
        draft['tests'] = []
    else:
        draft['tests'] *= 2
    assert restore(draft, saved, binding) == (draft, [])


def test_unknown_and_duplicate_predictions_are_not_silently_removed():
    spec, saved = accepted()
    row = {**spec['baseline_expectations'][0], 'goal_quote': 'wrong'}
    unknown = {'node': 'tests/test_old.py::not_collected'}
    draft = {**spec, 'baseline_expectations': [row, row, unknown]}
    assert restore(draft, saved, saved['binding']) == (draft, [])
    assert capture({'tests': []}, goal='g', design={}, source_hashes={}) is None


def test_case_plan_and_baseline_intent_are_reused_together():
    from plugins.development_quality.src.baseline_expectations import compare
    spec, _ = accepted()
    spec['baseline_expectations'][0]['classification'] = 'feature_control'
    node = spec['baseline_expectations'][0]['node']
    spec['case_plan'] = [{'node': node, 'kind': 'boundary', 'behavior': 'zero'}]
    saved = capture(spec, goal='preserve zero', design={}, source_hashes={})
    draft = deepcopy(spec)
    draft['case_plan'][0]['kind'] = 'preservation'
    outcomes = {'tests.test_old::test_old': 'passed'}
    assert compare(draft, outcomes)['status'] == 'rejected'
    result, changes = restore(draft, saved, saved['binding'])
    assert result == spec and changes[0]['field'] == 'case_plan'
    assert compare(result, outcomes)['status'] == 'matched'


def test_reused_metadata_enters_fresh_semantic_audit(tmp_path):
    from runtime.feature_quality_chat import QualityChat
    from runtime.feature_quality_draft import draft_binding
    from runtime.narrow_type_evidence_binding import content_digest
    from runtime.local_inference import LocalInferenceConfig
    from tests.runtime.test_feature_development import spec
    from tests.runtime.test_feature_quality import augment
    proposal = augment('spec_writer', spec())
    for row in proposal['case_plan']:
        if row['kind'] == 'preservation':
            row['node'] = proposal['tests'][0]['path'] + '::test_negative'
    proposal['baseline_expectations'] = [{'node': proposal['tests'][0]['path'] + '::test_negative',
        'classification': 'preservation', 'reason': 'preserve zero', 'goal_quote': 'zero',
        'source_evidence': [{'path': 'engine.py', 'quote': 'return value'}]}]
    expected = {'engine.py': 'bound'}
    payload = {'goal': 'zero and negative labels', 'artifacts': {'architect': {}},
        'source_inventory_digest': content_digest(expected),
        'sources': [{'path': 'engine.py', 'content': 'return value'}]}
    calls = []
    def chat(messages, *, config):
        calls.append(config.provider_label)
        assert config.provider_label == 'quality:spec_auditor'
        audit_payload = json.loads(messages[1]['content'])
        assert audit_payload['specification']['baseline_expectations'] == proposal['baseline_expectations']
        return {'decision': 'approve'}
    q = QualityChat(chat, tmp_path, expected=expected, require_baseline_expectations=True)
    q.freeze_specification(proposal, goal=payload['goal'], design={})
    draft = deepcopy(proposal); draft['baseline_expectations'][0]['goal_quote'] = '...zero'
    q.unaccepted['spec_writer'] = {'binding': draft_binding(payload, 'spec_writer'), 'proposal': draft}
    result = q([{'role': 'system', 'content': 'writer'}, {'role': 'user', 'content': json.dumps(payload)}],
        config=LocalInferenceConfig('http://unused', 'fake', provider_label='feature:spec_writer'))
    assert calls == ['quality:spec_auditor'] and result == proposal
    assert (tmp_path / 'accepted-metadata-0-0.json').exists()


@pytest.mark.parametrize('tamper', [False, True])
@pytest.mark.parametrize('legacy_label', [False, True])
def test_rejected_audit_resume_reconstructs_qualified_metadata_from_checkpoint(tmp_path, tamper, legacy_label):
    import sys
    from pathlib import Path
    from runtime.feature_acceptance import save
    from runtime.feature_development import run_feature_development
    from runtime.feature_quality_chat import QualityChat
    from runtime.feature_quality_resume import restore_spec_draft
    from runtime.feature_workspace import inventory
    from runtime.narrow_type_evidence_binding import content_digest
    from runtime.local_inference import LocalInferenceConfig
    from tests.runtime.test_feature_development import fake_chat
    project = tmp_path / 'source'
    (project / 'tests').mkdir(parents=True)
    (project / 'engine.py').write_text('def display(value):\n    return str(value)\n')
    (project / 'tests/test_existing.py').write_text('def test_existing():\n    assert True\n')
    delegate = fake_chat(project)
    def chat(messages, *, config):
        response = delegate(messages, config=config)
        if config.provider_label == 'feature:spec_writer':
            response['baseline_expectations'] = [{'node': 'tests/test_labels.py::test_negative',
                'classification': 'feature_gap', 'reason': 'goal', 'goal_quote': 'goal',
                'source_evidence': [{'path': 'engine.py', 'quote': 'return str(value)'}]}]
            response['case_plan'] = [{'node': 'tests/test_labels.py::test_negative',
                                     'kind': 'feature_gap' if legacy_label else 'feature', 'behavior': 'negative labels'}]
        return response
    prior = tmp_path / 'old/run/cycle-0'
    config = LocalInferenceConfig('http://unused', 'fake')
    report = run_feature_development(project=project, work=prior, goal='goal', python=Path(sys.executable),
        chat=chat, configs={r: config for r in ('analyzer', 'architect', 'spec_writer')})
    assert report['status'] == 'verified'
    qualified = report['artifacts']['spec_writer']
    expected = inventory(project)
    checkpoint = prior.parent / 'cycle-1'
    roles = {r: report['artifacts'][r] for r in ('analyzer', 'architect')}
    save(checkpoint / 'report.json', {'project': str(project), 'goal': 'goal', 'artifacts': roles, 'attempts': []})
    save(checkpoint / 'source-inventory.json', expected)
    for role, value in roles.items():
        save(checkpoint / (role + '.json'), value)
    save(prior.parent / 'report.json', {'goal': 'goal', 'source_hashes': expected,
        'cycles': [{'checkpoint': str(prior)}, {'checkpoint': str(checkpoint)}]})
    payload = {'goal': 'goal', 'artifacts': roles, 'source_inventory_digest': content_digest(expected),
        'immutable_previous_tests': qualified['tests'],
        'immutable_baseline_expectations': [] if tamper else qualified['baseline_expectations'],
        'immutable_case_plan': qualified['case_plan']}
    draft = {**qualified, 'baseline_expectations': [], 'case_plan': []}
    audited = deepcopy(qualified)
    if legacy_label:
        audited['case_plan'][0]['kind'] = 'boundary'
        draft['case_plan'] = deepcopy(audited['case_plan'])
    rows = []
    for role, request, response in [
        ('feature:spec_writer', payload, draft),
        ('quality:spec_auditor', {'goal': 'goal', 'design': roles['architect'], 'specification': audited,
                                'accepted_metadata_contract': 'qualified_label_repair.v1' if legacy_label else 'legacy'},
         {'decision': 'reject', 'issues': ['add missing case']})]:
        messages = [{'role': 'system', 'content': role}, {'role': 'user', 'content': json.dumps(request)}]
        rows.append({'status': 'returned', 'request_digest': content_digest(messages), 'messages': messages,
                     'raw_response': response, 'telemetry': [{'provider_label': role}]})
    save(prior.parent.parent / 'transcript.json', rows)
    q = QualityChat(None, tmp_path / 'new')
    if tamper:
        with pytest.raises(ValueError, match='accepted_metadata_mismatch'):
            restore_spec_draft(q, checkpoint, project, expected, 'goal')
    else:
        restore_spec_draft(q, checkpoint, project, expected, 'goal')
        assert q.pending['spec_writer']['feedback']['rejected'] == audited
    assert not q.retained  # Neither saved nor reconstructed metadata grants approval.
