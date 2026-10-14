"""Native fixture execution, explicit capture and evidence-bound diagnostic input."""
import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from runtime.native_failure_acceptance import _probe
from runtime.project_failure_evidence_packet import build_failure_evidence_packet
from runtime.project_native_failure_binding import _interpret_pytest_result
from runtime.native_repair_observations import collect_native_repair_observations
from runtime.repair_observations import validate_repair_observations, observation_context
from runtime.repair_diagnostic_context import diagnostic_context
from runtime.narrow_type_evidence_binding import content_digest


@pytest.fixture(scope='module')
def case(tmp_path_factory):
    root = tmp_path_factory.mktemp('native-observations')
    project = root / 'project'
    project.mkdir()
    (project / 'core.py').write_text("class Worker:\n"
        "    def convert(self, value):\n        result = value + '-broken'\n        return result\n"
        "    def unused(self):\n        return 'unused'\n")
    (project / 'fixture.txt').write_text('fixture\n')
    (project / 'test_case.py').write_text('''from pathlib import Path
import pytest
from core import Worker

@pytest.fixture
def value(tmp_path):
    path = tmp_path / 'value.txt'
    path.write_text(Path(__file__).with_name('fixture.txt').read_text().strip())
    yield path.read_text()
    path.unlink()

@pytest.mark.parametrize('expected', ['fixed', 'fixture-broken'])
def test_case(value, expected):
    assert value == 'fixture'
    actual = Worker().convert(value)
    assert actual == expected
    assert Worker().convert(value) == expected
''')
    nodeids = ['test_case.py::test_case[fixed]']
    records = []
    for i in range(2):
        probe = _probe(project, root / f'intake-{i}', nodeids, [], 20, Path(sys.executable))
        output = Path(probe['output']).read_text(encoding='utf-8')
        records.append({**_interpret_pytest_result(project, probe['returncode'], output, {}), 'output': output})
    failure = {'target': 'core.py:Worker.convert', 'failure_signature': records[0]['failure_signature'],
        'failing_nodeids': nodeids, 'detail': records[0]['output'], 'failure_kind': 'test_failed'}
    packet = build_failure_evidence_packet(project_dir=project, failure=failure, chain_case={'repetitions': records})
    assert packet['status'] == 'complete'
    evidence = collect_native_repair_observations(project, packet, root / 'observations', authorized=True,
        method_fields={'core.py:Worker.convert': ['value', 'result']}, test_local_names=['value', 'actual', 'expected'])
    return project, packet, evidence


def test_parameterized_fixture_runs_once_without_evaluating_unreached_assertion(case):
    project, packet, evidence = case
    validate_repair_observations(project, packet, evidence)
    row = observation_context(evidence)['rows'][0]
    assert row['test_outcome'] == 'failed'
    assert [a['reachability'] for a in row['assertions']] == ['reached', 'reached', 'not_reached']
    assert len(row['calls']) == 1  # Third assertion must not execute its method call.
    assert row['calls'][0]['return']['value'] == 'fixture-broken'
    fields = row['assertions'][1]['snapshots'][0]['locals']
    assert fields['value']['value'] == 'fixture' and fields['actual']['value'] == 'fixture-broken'
    assert fields['expected']['value'] == 'fixed'
    for repeat in evidence['repeats']:
        assert not list((Path(repeat['path']).parent / 'tmp').rglob('value.txt'))
    assert evidence['execution_authorized'] is evidence['source_apply'] is False
    context = diagnostic_context({'failure_evidence_packet': packet, 'repair_observations': evidence}, project)
    assert 'native_test_observations' in context and 'isolated_assertion_observations' not in context


@pytest.mark.parametrize('mutation', ['values', 'probe', 'request', 'output', 'copy'])
def test_changed_native_evidence_is_rejected(case, tmp_path, mutation):
    project, packet, evidence = case
    changed = deepcopy(evidence)
    if mutation in {'values', 'probe'}:
        if mutation == 'values':
            for row in changed['repeats']:
                row['observation']['rows'][0]['assertions'][-1]['reachability'] = 'reached'
        else:
            changed['probe_hashes']['native_repair_observation_probe.py'] = '0' * 64
    else:
        # Isolate just this receipt copy, retaining original evidence for other tests.
        import shutil
        source = Path(changed['repeats'][0]['path']).parent
        control = tmp_path / 'control'
        shutil.copytree(source, control)
        changed['repeats'][0]['path'] = str(control / 'observation.json')
        request = json.loads((control / 'request.json').read_text())
        request['pytest_arguments'] = [v.replace(str(source), str(control)) for v in request['pytest_arguments']]
        (control / 'request.json').write_text(json.dumps(request))
        if mutation == 'request':
            request['test_local_names'] = ['invented']
            (control / 'request.json').write_text(json.dumps(request))
        elif mutation == 'output':
            (control / 'output.txt').write_text('invented native output')
        else:
            (control / 'project/fixture.txt').write_text('changed')
    changed['observations_digest'] = content_digest({k: v for k, v in changed.items() if k != 'observations_digest'})
    with pytest.raises(ValueError):
        validate_repair_observations(project, packet, changed)


@pytest.mark.parametrize('fields,locals_', [({'core.py:Worker.convert': ['self']}, []),
    ({'core.py:Worker.convert': ['invented']}, []), ({'else.py:Worker.convert': []}, []),
    ({'core.py:Worker.convert': []}, ['invented']), ({'core.py:Worker.convert': []}, ['actual'] * 9)])
def test_capture_scope_rejected_before_execution(case, tmp_path, fields, locals_):
    project, packet, _ = case
    work = tmp_path / 'never-created'
    with pytest.raises(ValueError):
        collect_native_repair_observations(project, packet, work, authorized=True,
            method_fields=fields, test_local_names=locals_)
    assert not work.exists()


def test_authorization_and_unexecuted_methods(case, tmp_path):
    project, packet, _ = case
    with pytest.raises(ValueError, match='authorization'):
        collect_native_repair_observations(project, packet, tmp_path / 'unauthorized', method_fields={})
    with pytest.raises(ValueError, match='did_not_reproduce'):
        collect_native_repair_observations(project, packet, tmp_path / 'unused', authorized=True,
                                          method_fields={'core.py:Worker.unused': []})
    assert json.loads((tmp_path / 'unused/result.json').read_text())['status'] == 'blocked'


def test_compact_context_losslessly_retains_events_and_values(case):
    _, _, evidence = case
    original = observation_context(evidence)
    compact = observation_context(evidence, compact=True)
    assert 'locals_encoding' in compact
    rebuilt = deepcopy(compact['rows'])
    for row in rebuilt:
        for call in row['calls']:
            values = {}
            for event in call['events']:
                values.update(event['locals'])
                event['locals'] = deepcopy(values)
    assert rebuilt == original['rows']
    assert len(json.dumps(compact['rows'])) < len(json.dumps(original['rows']))
    assert observation_context(evidence) == original
