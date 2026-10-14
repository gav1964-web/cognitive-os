"""Preservation examples reach both model steps without pretending they passed."""
import json
from copy import deepcopy

import pytest

from runtime.requested_acceptance_context import requested_acceptance_context
from runtime.upstream_task_contract import normalize_task_contract
from runtime.project_development_llm_hypothesis import build_llm_failure_hypothesis
from runtime.upstream_llm_candidates import candidate_messages
from tests.runtime.test_project_development_llm_hypothesis import _issue, _project, _payload, _config


@pytest.mark.parametrize('requirements', [None, 'Advisory description', [], [None],
    [{'acceptance_examples': 'claimed passing tests'}], [{'acceptance_examples': ['passed']}]] )
def test_advisory_contract_never_claims_native_evidence(tmp_path, requirements):
    contract = {'contract_digest': 'advisory', 'requirements': requirements}
    result = requested_acceptance_context(tmp_path / 'not_read', contract)
    assert result['status'] == 'not_applicable'
    assert result['authority'] == 'no_native_acceptance_evidence'
    assert 'bindings' not in result and 'test_sources' not in result


def setup(tmp_path):
    project = _project(tmp_path)
    (project/'tests').mkdir()
    (project/'tests/test_module.py').write_text(
        "import pytest\nfrom module import parse_value\n"
        "def test_empty_value():\n    assert parse_value('') == ''\n"
        "@pytest.mark.parametrize('value', ['x:y', 'z:y'])\n"
        "def test_preserve(value):\n    assert parse_value(value) == 'y'\n", encoding='utf-8')
    contract = normalize_task_contract({'schema_version':'upstream_task_contract.v1',
        'origin':'user_supplied','change_kind':'defect','constraints':[], 'requirements':[
            {'id': ident,'statement': ident,'targets':['module.py:parse_value'], 'acceptance_examples':[
                {'kind':'native_test','nodeid':'tests/test_module.py::'+node,
                 'expectation':'passes','baseline_expectation':expected}]}
            for ident,node,expected in [('FIX','test_empty_value','fails'),
                                        ('KEEP','test_preserve[x:y]','passes')]]})
    return project, contract


def test_hypothesis_and_candidate_receive_identical_preservation_source(tmp_path):
    project, contract = setup(tmp_path)
    issue = _issue()
    issue['requested_task_contract'] = contract
    captured = []
    def chat(messages, *, config):
        captured.append(json.loads(messages[1]['content']))
        return _payload()
    advisory = build_llm_failure_hypothesis(issue=issue, project_dir=project, config=_config(), chat=chat)
    assert advisory['status'] == 'accepted_hypothesis_only'
    context = captured[0]['requested_acceptance_context']
    assert 'declared_not_observed' in context['authority']
    preserve = context['test_sources'][1]
    assert "['x:y', 'z:y']" in preserve['excerpt']
    assert "parse_value(value) == 'y'" in preserve['excerpt']
    packet = {'target':'module.py:parse_value','test_sources':[]}
    messages = candidate_messages(packet, advisory, (project/'module.py').read_text())
    assert json.loads(messages[1]['content'])['requested_acceptance_context'] == context
    preserve['excerpt'] = 'tampered after advisory'
    assert advisory['requested_acceptance_context'] != context


def test_direct_route_receives_same_source_contract(tmp_path):
    from runtime.upstream_direct_proposals import direct_candidate_messages
    project, contract = setup(tmp_path)
    issue = _issue()
    issue['requested_task_contract'] = contract
    issue['failure_evidence_packet'] = {'target':'module.py:parse_value'}
    messages, descriptor = direct_candidate_messages(issue, project)
    context = json.loads(messages[1]['content'])['requested_acceptance_context']
    assert context == requested_acceptance_context(project, contract)
    assert descriptor['repair_design']['execution_authority'] is False


def test_source_change_invalidates_context_digest(tmp_path):
    project, contract = setup(tmp_path)
    before = requested_acceptance_context(project, contract)
    path = project/'tests/test_module.py'
    path.write_text(path.read_text().replace("== 'y'", "== 'other'"))
    after = requested_acceptance_context(project, contract)
    assert after['context_digest'] != before['context_digest']
    assert after['bindings'][1]['source_sha256'] != before['bindings'][1]['source_sha256']


@pytest.mark.parametrize('node', ['tests/test_module.py::missing', '../secret.py::test_secret'])
def test_missing_or_escaping_test_is_not_presented_as_evidence(tmp_path, node):
    project, contract = setup(tmp_path)
    contract = deepcopy(contract)
    contract['requirements'][1]['acceptance_examples'][0]['nodeid'] = node
    with pytest.raises(ValueError):
        requested_acceptance_context(project, contract)
