"""Module-function diagnostics retain native outcomes and source identities."""
import json
import sys
from pathlib import Path

import pytest

from runtime.native_failure_acceptance import _probe
from runtime.native_repair_observations import collect_native_repair_observations
from runtime.native_repair_observation_probe import observation_catalog, NativeTracker
from runtime.project_failure_evidence_packet import build_failure_evidence_packet
from runtime.project_native_failure_binding import _interpret_pytest_result
from runtime.repair_observations import validate_repair_observations, observation_context


def test_module_function_records_tuple_values_and_reached_branch(tmp_path):
    project = tmp_path / 'project'
    project.mkdir()
    (project/'core.py').write_text('def convert(rows):\n    first = rows[0]\n    return first\n')
    (project/'test_case.py').write_text("from core import convert\ndef test_case():\n"
        "    assert convert([('a', 2)]) == 2\n    assert convert([('b', 3)]) == 3\n")
    records = []
    for index in range(2):
        probe = _probe(project, tmp_path/f'intake-{index}', ['test_case.py::test_case'], [], 20, Path(sys.executable))
        output = Path(probe['output']).read_text(encoding='utf-8')
        records.append({**_interpret_pytest_result(project, probe['returncode'], output, {}), 'output': output})
    failure = {'target': 'core.py:convert', 'failure_signature': records[0]['failure_signature'],
               'failing_nodeids': ['test_case.py::test_case'], 'detail': records[0]['output']}
    packet = build_failure_evidence_packet(project_dir=project, failure=failure, chain_case={'repetitions': records})
    evidence = collect_native_repair_observations(project, packet, tmp_path/'observations', authorized=True,
                                                 method_fields={'core.py:convert': ['rows', 'first']})
    validate_repair_observations(project, packet, evidence)
    row = observation_context(evidence)['rows'][0]
    assert [a['reachability'] for a in row['assertions']] == ['reached', 'not_reached']
    assert len(row['calls']) == 1 and row['test_outcome'] == 'failed'
    call = row['calls'][0]
    assert call['return']['type'] == 'tuple'
    assert call['events'][-1]['locals']['first'] == call['return']
    assert evidence['source_unchanged'] and evidence['execution_authorized'] is False


@pytest.mark.parametrize('source', [
    '@decorator\ndef convert(x):\n    return x\n',
    'async def convert(x):\n    return x\n',
    'def convert(x):\n    yield x\n',
    'def convert(x):\n    return x\ndef convert(x):\n    return 1\n',
])
def test_unsupported_function_identity_is_rejected(source):
    with pytest.raises(ValueError):
        observation_catalog(source, 'core.py:convert')


def test_replacement_code_with_same_name_is_rejected(tmp_path):
    source = 'def convert(x):\n    return x\n'
    (tmp_path/'core.py').write_text(source)
    tracker = NativeTracker(tmp_path, {'observed_target': 'core.py:convert',
        'method_fields': {'core.py:convert': []}, 'tests': [], 'test_local_names': []})
    namespace = {}
    exec(compile('def convert(x):\n    return x + 1\n', str(tmp_path/'core.py'), 'exec'), namespace)
    tracker.active = {'calls': [], 'assertions': []}
    tracker.test_code = None
    try:
        sys.settrace(tracker.trace)
        with pytest.raises(ValueError, match='observed_method_code_changed'):
            namespace['convert'](2)
    finally:
        sys.settrace(None)
