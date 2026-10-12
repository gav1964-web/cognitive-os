"""Draft point edits preserve coverage and remain behind ordinary admission gates."""
import json
from copy import deepcopy
import pytest

from runtime.feature_spec_delta import descriptor, expand
from runtime.feature_quality_draft import draft_binding
from runtime.feature_quality_chat import QualityChat
from runtime.feature_quality_resume import restore_spec_draft
from runtime.feature_test_references import compact_test_references
from runtime.feature_acceptance import save
from runtime.local_inference import LocalInferenceConfig
from runtime.narrow_type_evidence_binding import content_digest
from tests.runtime.test_feature_development import spec, project, fake_chat, run
from tests.runtime.test_feature_quality import augment
from tests.runtime.test_feature_quality_resume import receipt


def context():
    base = augment('spec_writer', spec())
    return {'goal': 'labels', 'artifacts': {'architect': {}}, 'sources': [],
            'source_inventory_digest': 'source',
            'quality_contract_feedback': {'rejected': base, 'issues': []}}


def delta(payload):
    desc = descriptor(payload)
    payload['specification_delta_base'] = desc
    return {'status': 'ready', 'specification_delta': {
        **{k: desc[k] for k in ('contract', 'base_digest', 'binding_digest')},
        'tests': [], 'set_fields': {}}}


def test_point_edit_and_add_preserve_other_files_and_fields():
    payload = context(); base = payload['quality_contract_feedback']['rejected']
    base['tests'].append({'path': 'tests/test_keep.py', 'content': '# exact bytes\r\n'})
    result = delta(payload)
    result['specification_delta']['tests'] = [
        {'op': 'edit', 'path': base['tests'][0]['path'],
         'before_sha256': payload['specification_delta_base']['tests'][0]['content_sha256'],
         'replacements': [{'old': 'display(-2)', 'new': 'display(-3)'}]},
        {'op': 'add', 'path': 'tests/test_extra.py', 'content': 'def test_extra(): pass\n'}]
    expanded = expand(result, payload)
    assert expanded['tests'][1] == base['tests'][1]
    assert expanded['tests'][0]['content'] == base['tests'][0]['content'].replace('display(-2)', 'display(-3)')
    assert {k: v for k, v in expanded.items() if k != 'tests'} == {k: v for k, v in base.items() if k != 'tests'}
    assert len(base['tests']) == 2  # No in-place mutation of saved evidence.


@pytest.mark.parametrize('bad', ['base', 'goal', 'design', 'source', 'hash', 'duplicate',
                               'escape', 'frozen', 'delete', 'metadata', 'ambiguous', 'mixed'])
def test_invalid_delta_cannot_hide_drift_or_overwrite_frozen(bad):
    payload = context(); result = delta(payload); d = result['specification_delta']
    test = payload['quality_contract_feedback']['rejected']['tests'][0]
    op = {'op': 'edit', 'path': test['path'],
          'before_sha256': payload['specification_delta_base']['tests'][0]['content_sha256'],
          'replacements': [{'old': 'display(-2)', 'new': 'display(-3)'}]}
    d['tests'] = [op]
    if bad == 'base': test['content'] += '# drift'
    elif bad == 'goal': payload['goal'] = 'other'
    elif bad == 'design': payload['artifacts']['architect'] = {'design': 'other'}
    elif bad == 'source': payload['source_inventory_digest'] = 'other'
    elif bad == 'hash': op['before_sha256'] = 'other'
    elif bad == 'duplicate': d['tests'].append(deepcopy(op))
    elif bad == 'escape': d['tests'] = [{'op': 'add', 'path': 'tests/../prod.py', 'content': 'pass'}]
    elif bad == 'frozen': payload['immutable_previous_tests'] = [test]
    elif bad == 'delete': d['tests'] = [{'op': 'delete', 'path': test['path']}]
    elif bad == 'metadata': d['set_fields'] = {'tests': []}
    elif bad == 'ambiguous': op['replacements'][0]['old'] = 'display'
    else: result['tests'] = []
    with pytest.raises(ValueError, match='quality_spec_delta_'):
        expand(result, payload)


def test_lossless_input_references_still_bind_delta():
    payload = context(); base = payload['quality_contract_feedback']['rejected']
    base['tests'][0]['content'] += '# annotation\n' * 100
    payload['immutable_previous_tests'] = deepcopy(base['tests'])
    result = delta(payload)
    compacted, count = compact_test_references(payload)
    assert count == 1 and expand(result, compacted) == base


def test_invalid_delta_repair_then_complete_draft_is_audited(tmp_path):
    payload = context(); base = payload['quality_contract_feedback']['rejected']; calls = []
    def transport(messages, *, config):
        incoming = json.loads(messages[1]['content']); calls.append(config.provider_label)
        if config.provider_label == 'quality:spec_auditor':
            assert incoming['specification'] == base
            return {'decision': 'approve'}
        response = delta(incoming)
        if len(calls) == 1:
            response['specification_delta']['base_digest'] = 'wrong'
        else:
            assert incoming['specification_delta_feedback']['reason'] == 'quality_spec_delta_identity'
        return response
    q = QualityChat(transport, tmp_path)
    q.pending['spec_writer'] = {'binding': draft_binding(payload, 'spec_writer'),
                               'feedback': payload.pop('quality_contract_feedback')}
    value = q([{'role': 'system', 'content': 'spec'},
               {'role': 'user', 'content': json.dumps(payload)}],
        config=LocalInferenceConfig('http://unused', 'fake', provider_label='feature:spec_writer'))
    assert value == base and not q.frozen
    assert calls == ['feature:spec_writer', 'feature:spec_writer', 'quality:spec_auditor']


@pytest.mark.parametrize('audited', [True, False])
@pytest.mark.parametrize('tamper', [None, 'goal', 'body'])
def test_resume_reconstructs_delta_before_audit_identity_check(tmp_path, audited, tamper):
    project, expected, prior, rows = receipt(tmp_path)
    roles = json.loads((prior / 'report.json').read_text())['artifacts']
    base = deepcopy(rows[0]['raw_response'])
    payload = {'goal': 'goal', 'artifacts': roles, 'source_inventory_digest': content_digest(expected),
               'quality_contract_feedback': {'rejected': base}}
    response = delta(payload)
    response['specification_delta']['set_fields'] = {'limitations': ['still needs qualification']}
    normalized = expand(response, payload)
    if tamper == 'goal': payload['goal'] = 'other'
    if tamper == 'body': base['tests'][0]['content'] += 'changed'
    rows[0]['messages'][1]['content'] = json.dumps(payload)
    rows[0]['raw_response'] = response
    audit = json.loads(rows[1]['messages'][1]['content']); audit['specification'] = normalized
    rows[1]['messages'][1]['content'] = json.dumps(audit)
    for row in rows: row['request_digest'] = content_digest(row['messages'])
    save(prior.parent.parent / 'transcript.json', rows if audited else rows[:1])
    q = QualityChat(None, tmp_path / 'new')
    if tamper:
        with pytest.raises(ValueError): restore_spec_draft(q, prior, project, expected, 'goal')
    else:
        restore_spec_draft(q, prior, project, expected, 'goal')
        assert (q.pending['spec_writer']['feedback']['rejected'] if audited
                else q.unaccepted['spec_writer']['proposal']) == normalized
    assert not q.frozen and not q.retained


@pytest.mark.parametrize('wrong_expectation', [False, True])
def test_expanded_delta_still_requires_native_candidate_checks(project, tmp_path, wrong_expectation):
    delegate = fake_chat(project); writers, audits = [], []
    def transport(messages, *, config):
        role = config.provider_label.partition(':')[2]
        payload = json.loads(messages[1]['content'])
        if role == 'design_auditor': return {'decision': 'approve'}
        if role == 'spec_auditor':
            audits.append(payload['specification'])
            return {'decision': 'reject' if len(audits) == 1 else 'approve',
                    'issues': [{'reason': 'Exercise another negative value'}]}
        if role == 'spec_writer':
            writers.append(1)
            if len(writers) > 1:
                response = delta(payload)
                response['specification_delta']['tests'] = [{
                    'op': 'edit', 'path': 'tests/test_labels.py',
                    'before_sha256': payload['specification_delta_base']['tests'][0]['content_sha256'],
                    'replacements': [{'old': 'display(-2) == "(2)"',
                                      'new': 'display(-3) == "(7)"' if wrong_expectation else 'display(-3) == "(3)"'}]}]
                return response
        return augment(role, delegate(messages, config=config))
    q = QualityChat(transport, tmp_path / 'quality')
    result = run(project, tmp_path, chat=q)
    assert len(writers) == 2 and len(audits) == 2
    assert 'display(-3)' in audits[-1]['tests'][0]['content']
    assert result['status'] == ('blocked' if wrong_expectation else 'verified')
    assert not result['source_apply']
    if wrong_expectation:
        assert not any(a['passed'] for a in result['attempts'])
        assert 'reviewer' not in result['artifacts']
    else:
        assert result['attempts'][0]['passed']
