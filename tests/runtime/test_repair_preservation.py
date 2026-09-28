"""Preservation is native existing-test evidence, never a model's self-rating."""
from copy import deepcopy
from pathlib import Path

import pytest

from runtime.local_inference import LocalInferenceConfig
from runtime.narrow_type_evidence_binding import content_digest
from runtime.repair_preservation import (
    collect_preservation_evidence, validate_preservation, preservation_context,
    validate_preservation_plan, bind_preservation,
)
from runtime.repair_trial_binding import build_repair_trial_packet, bind_repair_diagnosis
from runtime.upstream_llm_trials import validate_llm_diagnosis_proposals
from runtime.stage_finalization_workspace import inventory, snapshot
from tests.runtime.test_repair_function_nomination import prepare_functions, bundle_for
from tests.runtime.test_repair_trial_binding import issue_for


@pytest.fixture(scope='module')
def preservation_case(tmp_path_factory):
    root = tmp_path_factory.mktemp('preservation')
    project, observation = prepare_functions(root, generator=False, body="    assert render('bad') == 'fixed'\n")
    bundle = bundle_for(project, observation, root)
    packet = build_repair_trial_packet(project=project, observation=observation, bundle=bundle)
    evidence = collect_preservation_evidence(project=project, packet=packet,
        nodeids=['tests/test_case.py::test_preserved'], work_dir=root / 'preserved', authorized=True)
    assert evidence['status'] == 'verified_baseline', evidence
    return project, observation, bundle, packet, evidence


def test_existing_passing_test_retained_without_rewriting_failure(preservation_case):
    project, observation, bundle, packet, evidence = preservation_case
    validate_preservation(packet, evidence, project)
    diagnosis = bind_repair_diagnosis({'issues': [issue_for(observation)]}, project=project, bundle=bundle)
    bound = bind_preservation(diagnosis, project, evidence)
    assert bound['issues'][0]['failure_evidence_packet'] == packet
    assert 'preservation_evidence' not in diagnosis['issues'][0]
    assert preservation_context(evidence)['cases'][0]['source'].startswith('def test_preserved')


@pytest.mark.parametrize('mutation', ['packet', 'skip', 'parameters', 'authority', 'source'])
def test_altered_preservation_evidence_rejected(preservation_case, mutation):
    project, _, _, packet, original = preservation_case
    evidence = deepcopy(original)
    if mutation == 'packet':
        evidence['packet_digest'] = 'invented'
    elif mutation == 'skip':
        for p in evidence['probes']:
            p['data']['reports'][1]['outcome'] = 'skipped'
    elif mutation == 'parameters':
        for p in evidence['probes']:
            p['data']['cases'][0]['parameters'] = {'expected': 'forged'}
    elif mutation == 'authority':
        evidence['execution_authorized'] = True
    else:
        evidence['test_sources'][0]['source'] = 'assert True'
    evidence['digest'] = content_digest({k: v for k, v in evidence.items() if k != 'digest'})
    with pytest.raises(ValueError):
        validate_preservation(packet, evidence, project)


@pytest.mark.parametrize('plan', [None, [], [{'case_id': 'P002', 'behavior': 'Keep existing public behavior.'}],
    [{'case_id': 'P001', 'behavior': 'ok'}], [{'case_id': 'P001', 'behavior': 'Keep existing public behavior.', 'source_apply': True}]])
def test_plan_must_cover_exact_cases(preservation_case, plan):
    with pytest.raises(ValueError, match='complete_preservation_plan_required'):
        validate_preservation_plan(preservation_case[-1], plan)


def test_stale_project_and_unauthorized_collection_rejected(preservation_case, tmp_path):
    project, _, _, packet, evidence = preservation_case
    with pytest.raises(ValueError, match='authorization'):
        collect_preservation_evidence(project=project, packet=packet, nodeids=evidence['nodeids'], work_dir=tmp_path/'denied')
    copy = tmp_path/'copy'
    snapshot(project, copy, inventory(project))
    (copy/'callbacks.py').write_text('def convert(value): return value\n')
    with pytest.raises(ValueError, match='stale_preservation_source'):
        validate_preservation(packet, evidence, copy)


@pytest.mark.parametrize('bad_plan,bad_patch', [(True, False), (False, True), (False, False)])
def test_native_preservation_blocks_regressive_model_candidate(preservation_case, tmp_path, bad_plan, bad_patch):
    project, observation, bundle, packet, evidence = preservation_case
    diagnosis = bind_preservation(bind_repair_diagnosis({'issues': [issue_for(observation)]},
        project=project, bundle=bundle), project, evidence)
    calls = []
    def chat(messages, *, config):
        import json
        context = json.loads(messages[1]['content'])
        if 'preservation_context' in context:
            calls.append('design')
            answer = {'target': packet['target'], 'failure_signature': packet['failure_signature'],
                'mechanism': 'The callback returns an incorrect value for the bad input.',
                'repair_mechanism': 'Change only the bad input branch and preserve other inputs.',
                'mutation_contract': {'precondition': 'The bad input reaches the callback.',
                    'change': 'Return the fixed value for that branch.', 'preserved_behavior': 'Keep the good input returning good.'},
                'confidence': 0.8, 'residual_risks': ['Existing regression tests remain required.']}
            if not bad_plan:
                answer['preservation_plan'] = [{'case_id': 'P001', 'behavior': 'Preserve the good input result by limiting the changed branch.'}]
            return answer
        calls.append('candidate')
        assert context['design']['preservation_evidence'] == evidence
        return {'candidates': [{'id': 'repair', 'reason': 'Repair the callback under native tests.',
            'replacement_source': "def convert(value):\n    return 'fixed'" + ('' if bad_patch else " if value == 'bad' else value") + '\n'}]}
    result = validate_llm_diagnosis_proposals(diagnosis, project=project, root=tmp_path, authorized=True,
        delivery_authorized=True, config=LocalInferenceConfig(base_url='http://example.invalid', model='scripted'), chat=chat)
    issue = result['issues'][0]
    if bad_plan:
        assert calls == ['design']
        assert 'complete_preservation_plan_required' in issue['llm_candidate_trial']['reason']
    elif bad_patch:
        assert calls == ['design', 'candidate']
        assert issue['causal_comparison']['attempts'][0]['outcome'] == 'contradicted_by_preservation_tests'
        assert issue['causal_feedback']['role'] == 'architect'
        assert 'model_delivery' not in issue
    else:
        assert issue['llm_candidate_trial']['status'] == 'model_candidate_replay_ready', issue['llm_candidate_trial']
        assert issue['causal_comparison']['attempts'][0]['preservation_check']['status'] == 'passed'
        from runtime.upstream_model_delivery import selected_model_candidate
        changed = deepcopy(issue['causal_comparison'])
        changed['attempts'][0].pop('preservation_check')
        changed['comparison_digest'] = content_digest({k: v for k, v in changed.items() if k != 'comparison_digest'})
        with pytest.raises(ValueError, match='preservation_not_verified'):
            selected_model_candidate(changed, packet)


def test_nonliteral_parameters_do_not_call_user_repr():
    from runtime.repair_preservation_probe import literal
    class Unknown:
        def __repr__(self):
            pytest.fail('custom repr executed')
    with pytest.raises(ValueError, match='nonliteral'):
        literal(Unknown())


@pytest.mark.parametrize('mark,passes', [('', True), ('@pytest.mark.skip', False), ('@pytest.mark.xfail', False)])
def test_parameters_are_captured_and_skip_xfail_are_not_baseline_passes(tmp_path, mark, passes):
    import sys
    from runtime.repair_preservation import _probe, _passed
    project = tmp_path/'project'
    project.mkdir()
    (project/'pytest.ini').write_text('[pytest]\n')
    (project/'test_native.py').write_text('import pytest\n' + mark + '\n'
        "@pytest.mark.parametrize(('value','expected'), [('example', 'example')], ids=['literal'])\n"
        'def test_native(value, expected):\n    assert value == expected\n')
    nodes = ['test_native.py::test_native[literal]']
    before = inventory(project)
    probe = _probe(project, tmp_path/'probe', nodes, Path(sys.executable))
    probe['copy_unchanged'] = inventory(project) == before
    assert probe['data']['cases'][0]['parameters'] == {'value': 'example', 'expected': 'example'}
    assert _passed(probe, nodes) is passes
