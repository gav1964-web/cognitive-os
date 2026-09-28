"""Requirement evidence must expose deselection, interface drift and stale sources."""
from pathlib import Path

import pytest

from runtime.stage_finalization_workspace import inventory, snapshot
from runtime.upstream_change_impact import analyze_change_impact
from runtime.upstream_requested_acceptance import verify_requested_acceptance
from runtime.upstream_task_contract import normalize_task_contract


def inputs(tmp_path, deselect=False):
    source = tmp_path / 'source'
    (source / 'tests').mkdir(parents=True)
    (source / 'core.py').write_text('def read(x=1):\n    return x\n')
    (source / 'tests/test_core.py').write_text('from core import read\n'
        'def test_change():\n    assert read() == 2\n'
        'def test_keep():\n    assert read(0) == 0\n')
    if deselect:
        (source / 'conftest.py').write_text('def pytest_collection_modifyitems(items):\n'
            '    items[:] = [item for item in items if item.name != "test_keep"]\n')
    candidate = tmp_path / 'candidate'
    snapshot(source, candidate, inventory(source))
    (candidate / 'core.py').write_text('def read(x=1):\n    return x * 2\n')
    contract = normalize_task_contract({'schema_version': 'upstream_task_contract.v1',
        'origin': 'assistant_authored_development_fixture', 'change_kind': 'defect',
        'requirements': [{'id': name, 'statement': name, 'targets': ['core.py:read'],
            'acceptance_examples': [{'kind': 'native_test', 'nodeid': 'tests/test_core.py::test_' + name,
                                    'baseline_expectation': baseline, 'expectation': 'passes'}]}
            for name, baseline in [('change', 'fails'), ('keep', 'passes')]]})
    impact = analyze_change_impact(source, ['core.py:read'])
    return dict(project=source, patched=candidate, contract=contract, impact=impact, work_dir=tmp_path / 'checks')


def test_green_selected_subset_does_not_cover_all_requirements(tmp_path):
    args = inputs(tmp_path, deselect=True)
    result = verify_requested_acceptance(**args)
    assert result['probes'][1]['returncode'] == 0
    assert result['status'] == 'failed'
    assert not result['checks']['requested_nodes_executed']


def test_passing_examples_do_not_authorize_a_changed_parameter_name(tmp_path):
    args = inputs(tmp_path)
    (args['patched'] / 'core.py').write_text('def read(other=1):\n    return other * 2\n')
    result = verify_requested_acceptance(**args)
    assert result['checks']['requested_tests_passed']
    assert not result['checks']['interfaces_preserved']
    assert result['status'] == 'failed'


def test_impact_hashes_are_checked_before_test_execution(tmp_path):
    args = inputs(tmp_path)
    (args['project'] / 'core.py').write_text('def read(x=1):\n    return 0\n')
    with pytest.raises(ValueError, match='stale'):
        verify_requested_acceptance(**args)
    assert not args['work_dir'].exists()
