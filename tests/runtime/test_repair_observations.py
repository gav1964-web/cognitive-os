"""Isolated diagnostic observations remain distinct from native suite results."""
from copy import deepcopy

import pytest

from runtime.repair_observations import collect_repair_observations, validate_repair_observations, observation_context
from runtime.repair_observation_probe import safe_value
from runtime.stage_finalization_workspace import inventory
from runtime.narrow_type_evidence_binding import content_digest
from tests.runtime.test_repair_trial_binding import repair_case, evidence


def test_source_bound_observations_replay_each_assertion_without_modifying_source(repair_case, tmp_path):
    project, _, _, packet = repair_case
    before = inventory(project)
    result = collect_repair_observations(project, packet, tmp_path/'observations', authorized=True)
    validate_repair_observations(project, packet, result)
    rows = observation_context(result)['rows']
    assert [r['outcome'] for r in rows] == ['passed', 'failed']
    assert rows[1]['actual'] == {'type': 'str', 'value': 'broken'}
    assert rows[1]['expected'] == {'type': 'str', 'value': 'fixed'}
    assert rows[1]['distinct_calls'][0]['return'] == rows[1]['actual']
    assert result['execution_authorized'] is False
    assert inventory(project) == before
    changed = deepcopy(result)
    for repetition in changed['observations'][1]['repeats']:
        repetition['observation']['outcome'] = 'passed'
    changed['observations_digest'] = content_digest({k:v for k,v in changed.items() if k!='observations_digest'})
    with pytest.raises(ValueError, match='receipt_changed'):
        validate_repair_observations(project, packet, changed)
    changed = deepcopy(result); changed['argument_names'] = ['invented']
    changed['observations_digest'] = content_digest({k:v for k,v in changed.items() if k!='observations_digest'})
    with pytest.raises(ValueError, match='request_or_copy_changed'):
        validate_repair_observations(project, packet, changed)


def test_explicit_diagnostic_execution_required(repair_case, tmp_path):
    project, _, _, packet = repair_case
    with pytest.raises(ValueError, match='authorization'):
        collect_repair_observations(project, packet, tmp_path/'never-created')
    assert not (tmp_path/'never-created').exists()


def test_serializer_never_calls_custom_repr_or_iteration():
    class Unsafe:
        def __repr__(self): raise AssertionError('repr invoked')
        def __iter__(self): raise AssertionError('iteration invoked')
    class CustomSet(set):
        def __iter__(self): raise AssertionError('subclass iteration invoked')
    assert safe_value(Unsafe()) == {'type': 'opaque', 'value_omitted': True}
    assert safe_value(CustomSet())['type'] == 'opaque'
    assert safe_value({'h1', '_inline'}) == {'type': 'set', 'value': ['_inline', 'h1']}
    assert safe_value('x'*401)['value_omitted'] is True


def test_diagnostics_do_not_grant_model_trial_authority(tmp_path):
    from runtime.project_development import run_project_development
    with pytest.raises(ValueError, match='diagnostics_require'):
        run_project_development(root=tmp_path, project_dir=tmp_path, goal='inspect', repair_observations={})
