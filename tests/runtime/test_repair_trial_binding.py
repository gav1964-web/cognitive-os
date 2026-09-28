"""Derived repair evidence retains the observed API through native model delivery."""
from copy import deepcopy

import pytest

from runtime.native_failure_acceptance import run_native_acceptance
from runtime.project_failure_evidence_packet import is_complete_failure_evidence_packet, evidence_packet_digest
from runtime.repair_target_nomination import validate_nomination, _packet_contract
from runtime.repair_trial_binding import (
    build_repair_trial_packet, bind_repair_diagnosis, validate_repair_trial_source,
)
from runtime.stage_finalization_workspace import inventory, snapshot
from runtime.upstream_llm_trials import validate_llm_diagnosis_proposals
from runtime.local_inference import LocalInferenceConfig
from tests.runtime.test_repair_target_nomination import evidence, proposal


@pytest.fixture
def repair_case(evidence):
    project, observation, trace, context = evidence
    nomination = validate_nomination(proposal(context), project=project, packet=observation, trace=trace, context=context)
    bundle = {'nomination': nomination, 'trace': trace, 'context': context}
    packet = build_repair_trial_packet(project=project, observation=observation, bundle=bundle)
    return project, observation, bundle, packet


def issue_for(observation):
    return {'failure_specific_reducer_required': True, 'affected_targets': [observation['target']],
        'failure_evidence': [{'target': observation['target'], 'failure_signature': observation['failure_signature'],
            'failing_nodeids': observation['failing_nodeids']}], 'failure_evidence_packet': observation,
        'failure_evidence_packets': [observation], 'evidence': [observation['target']]}


def test_explicit_projection_preserves_observation_and_issue_history(repair_case):
    project, observation, bundle, packet = repair_case
    original = deepcopy(observation)
    diagnosis = {'issues': [issue_for(observation)]}
    bound = bind_repair_diagnosis(diagnosis, project=project, bundle=bundle)['issues'][0]
    assert observation == original
    assert packet['schema_version'] == 'repair_trial_packet.v1'
    assert packet['observation_packet'] == original
    assert packet['target'] == 'core.py:Worker.convert_bad'
    assert packet['failure_signature'] == original['failure_signature']
    assert packet['packet_digest'] != original['packet_digest']
    assert bound['failure_evidence'] == diagnosis['issues'][0]['failure_evidence']
    assert bound['failure_evidence_packets'] == [original]
    assert bound['affected_targets'] == [packet['target']]
    assert is_complete_failure_evidence_packet(packet, target=packet['target'])
    assert not is_complete_failure_evidence_packet(packet, target=original['target'])


@pytest.mark.parametrize('field,value', [
    ('target', 'core.py:Worker.unrelated'), ('failure_signature', 'invented'),
    ('failing_nodeids', []), ('test_sources', []), ('observed_failure', 'rewritten'),
    ('execution_authorized', True), ('observed_target', 'core.py:Worker.convert_bad'),
])
def test_rehashed_outer_packet_cannot_rewrite_observation(repair_case, field, value):
    _, _, _, packet = repair_case
    changed = deepcopy(packet)
    changed[field] = value
    changed['packet_digest'] = evidence_packet_digest(changed)
    assert not is_complete_failure_evidence_packet(changed, target=changed['target'])


def test_recursive_trial_packets_and_swapped_nomination_rejected(repair_case):
    project, observation, bundle, packet = repair_case
    with pytest.raises(ValueError, match='original_observation'):
        build_repair_trial_packet(project=project, observation=packet, bundle=bundle)
    bundle = deepcopy(bundle)
    bundle['nomination']['repair_target'] = 'core.py:Worker.unrelated'
    with pytest.raises(ValueError, match='outside_observed_call_scope'):
        build_repair_trial_packet(project=project, observation=observation, bundle=bundle)


def test_source_change_and_forged_target_excerpt_rejected(repair_case, tmp_path):
    project, _, _, packet = repair_case
    copy = tmp_path / 'changed'
    snapshot(project, copy, inventory(project))
    with (copy / 'tests/test_case.py').open('a', encoding='utf-8') as stream:
        stream.write('\n# stale\n')
    with pytest.raises(ValueError, match='stale_project_inventory'):
        validate_repair_trial_source(copy, packet)
    forged = deepcopy(packet)
    forged['target_source']['excerpt'] = 'def convert_bad(self): return "lie"'
    forged['packet_digest'] = evidence_packet_digest(forged)
    with pytest.raises(ValueError, match='source_or_binding_changed'):
        validate_repair_trial_source(project, forged)


@pytest.mark.parametrize('change', ['nodeids', 'observation', 'trace'])
def test_swapped_evidence_fails_before_model_calls(repair_case, tmp_path, monkeypatch, change):
    project, observation, bundle, _ = repair_case
    diagnosis = bind_repair_diagnosis({'issues': [issue_for(observation)]}, project=project, bundle=bundle)
    packet = diagnosis['issues'][0]['failure_evidence_packet']
    if change == 'nodeids':
        packet['failing_nodeids'] = ['tests/test_case.py::other']
    elif change == 'observation':
        packet['observation_packet']['failure_signature'] = 'different'
    else:
        packet['repair_nomination']['trace']['probe_source_sha256'] = '0' * 64
    packet['packet_digest'] = evidence_packet_digest(packet)
    monkeypatch.setattr('runtime.project_development_llm_hypothesis.call_json_chat',
        lambda *a, **kw: pytest.fail('invalid evidence reached model'))
    result = validate_llm_diagnosis_proposals(diagnosis, project=project, root=tmp_path,
        config=LocalInferenceConfig(base_url='http://example.invalid', model='scripted'), authorized=True)
    assert result['issues'][0]['llm_candidate_trial']['logical_model_calls'] == 0
    assert result['issues'][0]['llm_candidate_trial']['status'] == 'not_compared'


def test_nomination_cannot_enter_unvalidated_training_route(repair_case):
    _, _, _, packet = repair_case
    from runtime.project_development_experiment import _bounded_training_replay
    for authority in ['explicit_training_replay', 'explicit_llm_training_replay']:
        assert not _bounded_training_replay(intent={'authority': authority, 'target_symbol': packet['target']},
                                           packet=packet, allowed_operator_ids=[])


def test_core_rejects_nomination_without_model_trial(tmp_path):
    from runtime.project_development import run_project_development
    with pytest.raises(ValueError, match='repair_nomination_requires_authorized_model_trial'):
        run_project_development(root=tmp_path, project_dir=tmp_path, goal='repair', repair_nomination={})


def test_native_replay_uses_original_signature_but_only_changes_internal_method(repair_case, tmp_path):
    project, observation, _, packet = repair_case
    before = inventory(project)
    copy = tmp_path / 'patched'
    snapshot(project, copy, before)
    path = copy / 'core.py'
    from runtime.upstream_llm_candidates import _replacement
    path.write_text(_replacement(path.read_text(), packet['target'],
        "def convert_bad(self):\n    return 'fixed'\n"), encoding='utf-8')
    result = run_native_acceptance(source_project=project, patched_project=copy,
        contract=_packet_contract(packet), work_dir=tmp_path / 'accept')
    assert result['status'] == 'passed', (result['reason'], result['summary'])
    assert all(p['intake_signature'] == observation['failure_signature'] for p in result['probes'][:2])
    assert result['summary']['native_replay_targets'] == [packet['target']]
    assert inventory(project) == before
    path.write_text(path.read_text().replace("return 'unused'", "return 'also changed'"), encoding='utf-8')
    rejected = run_native_acceptance(source_project=project, patched_project=copy,
        contract=_packet_contract(packet), work_dir=tmp_path / 'reject')
    assert rejected['status'] == 'failed'
    assert 'outside_nominated_method' in rejected['reason']
    assert not rejected['probes']


@pytest.mark.parametrize('newline', ['\n', '\r\n'])
def test_exact_scope_handles_blank_lines_and_nonstandard_body_indent(repair_case, newline):
    _, _, _, packet = repair_case
    from tests.runtime.test_repair_target_nomination import PRODUCTION
    from runtime.upstream_llm_candidates import _replacement
    from runtime.repair_trial_binding import validate_repair_patch_scope
    source = PRODUCTION.replace('\n', newline)
    patch = _replacement(source, packet['target'], "def convert_bad(self):\n        value = 'fixed'\n\n        return value\n")
    validate_repair_patch_scope(source, patch, packet)


def provider(monkeypatch, packet):
    calls = []

    def hypothesis(messages, config):
        import json
        envelope = json.loads(messages[-1]['content'])
        assert envelope['target'] == packet['target']
        assert envelope['observed_target'] == packet['observed_target']
        methods = envelope['repair_call_context']['methods']
        original_methods = packet['repair_nomination']['context']['methods']
        if 'source_projection' in envelope['repair_call_context']:
            assert [{k:v for k,v in m.items() if k!='source'} for m in methods] == [
                {k:v for k,v in m.items() if k!='source'} for m in original_methods]
        else:
            assert methods == original_methods
        calls.append('hypothesis')
        return {'target': packet['target'], 'failure_signature': packet['failure_signature'],
            'mechanism': 'The internal bad converter returns the wrong result for the failing call.',
            'repair_mechanism': 'Correct the internal converter result while retaining the other dispatch branch.',
            'mutation_contract': {'precondition': 'The bad branch is selected by the observed API.',
                'change': 'Return the required fixed result from the internal method.',
                'preserved_behavior': 'The good dispatch branch and public API stay unchanged.'},
            'confidence': 0.8, 'residual_risks': ['Full native regression is still required.']}

    def candidates(messages, config):
        calls.append('candidate')
        return {'candidates': [{'id': 'internal', 'reason': 'Correct the internal result under native assertions.',
            'replacement_source': "def convert_bad(self):\n    return 'fixed'\n"}]}

    monkeypatch.setattr('runtime.project_development_llm_hypothesis.call_json_chat', hypothesis)
    monkeypatch.setattr('runtime.upstream_llm_trials.call_json_chat', candidates)
    return calls


def test_bound_model_trial_and_delivery_keep_immutable_observation(repair_case, tmp_path, monkeypatch):
    project, observation, bundle, packet = repair_case
    diagnosis = bind_repair_diagnosis({'issues': [issue_for(observation)]}, project=project, bundle=bundle)
    calls = provider(monkeypatch, packet)
    result = validate_llm_diagnosis_proposals(diagnosis, project=project, root=tmp_path,
        config=LocalInferenceConfig(base_url='http://example.invalid', model='scripted'),
        authorized=True, delivery_authorized=True)['issues'][0]
    assert calls == ['hypothesis', 'candidate']
    assert result['llm_candidate_trial']['status'] == 'model_candidate_replay_ready', [
        a.get('evidence', {}).get('reason') for a in result['causal_comparison'].get('attempts', [])]
    assert result['model_delivery']['target'] == packet['target']
    assert result['failure_evidence'] == diagnosis['issues'][0]['failure_evidence']
    from runtime.upstream_model_requirements import model_issue_intent
    from runtime.upstream_model_delivery import validate_delivery_source
    validate_delivery_source(project, model_issue_intent(result))
