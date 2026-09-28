from copy import deepcopy
import json
import pytest

from runtime.repair_diagnostic_context import enrich_diagnostic_envelope
from tests.runtime.test_repair_trial_binding import repair_case, evidence, issue_for


@pytest.mark.parametrize('callee', [
    'def parts(\n    self, rows: list[tuple[str, str]]\n) -> list[str]:\n    return []',
    'def parts(self, rows: list[tuple[str, str]]) -> list[str]: return []',
    'def parts(self, строки: list[tuple[str, str]]) -> list[str]: return []',
])
def test_direct_callee_container_contract_survives_body_projection(monkeypatch, callee):
    monkeypatch.setattr('runtime.repair_diagnostic_context.diagnostic_context', lambda *a: {'bound': True})
    envelope = {'target': 'm.py:C.repair', 'observed_target': 'm.py:C.api', 'repair_call_context': {
        'call_edges': [['m.py:C.api','m.py:C.repair'], ['m.py:C.repair','m.py:C.parts'],
                       ['m.py:C.parts','m.py:C.other']],
        'methods': [{'target':'m.py:C.api','source':'def api(self):\n    return self.repair()'},
                    {'target':'m.py:C.repair','source':'def repair(self):\n    return self.parts()'},
                    {'target':'m.py:C.parts','source':callee, 'code_digest':'unchanged'},
                    {'target':'m.py:C.other','source':'def other(self):\n    return []'}]}}
    original = deepcopy(envelope)
    enrich_diagnostic_envelope(envelope, {}, None)
    methods = envelope['repair_call_context']['methods']
    assert methods[0] == original['repair_call_context']['methods'][0]
    assert methods[1] == original['repair_call_context']['methods'][1]
    assert 'source' not in methods[2] and 'tuple[str, str]' in methods[2]['source_interface']
    assert 'return []' not in methods[2]['source_interface'] and methods[2]['interface_only']
    assert methods[2]['code_digest'] == 'unchanged'
    assert methods[2]['source_interface'].endswith('-> list[str]:')
    assert 'source' not in methods[3] and 'source_interface' not in methods[3]


def test_hypothesis_context_reaches_candidate_without_budget_bypass(repair_case, monkeypatch):
    from runtime.project_development_llm_hypothesis import build_llm_failure_hypothesis
    from runtime.upstream_llm_candidates import candidate_messages
    from runtime.local_inference import LocalInferenceConfig
    from tests.runtime.test_repair_grounding_feedback import hypothesis

    project, observation, bundle, packet = repair_case
    issue = issue_for(observation)
    issue.update(failure_evidence_packet=packet, affected_targets=[packet['target']])
    captured = []

    def respond(messages, *, config):
        captured.append(json.loads(messages[1]['content']))
        return hypothesis(packet)

    monkeypatch.setattr('runtime.project_development_llm_hypothesis.call_json_chat', respond)
    advisory = build_llm_failure_hypothesis(issue=issue, project_dir=project,
                                           config=LocalInferenceConfig(base_url='https://scripted.invalid', model='scripted'))
    assert advisory['status'] == 'accepted_hypothesis_only'
    source = (project / 'core.py').read_text(encoding='utf-8')
    candidate = json.loads(candidate_messages(packet, advisory, source)[1]['content'])
    assert candidate['repair_call_context'] == captured[0]['repair_call_context']
    assert candidate['repair_call_context']['nomination_digest'] == bundle['nomination']['nomination_digest']
    changed = deepcopy(advisory)
    changed['repair_call_context']['limitations'] = ['x' * 32001]
    with pytest.raises(ValueError, match='candidate_prompt_budget_exceeded'):
        candidate_messages(packet, changed, source)
