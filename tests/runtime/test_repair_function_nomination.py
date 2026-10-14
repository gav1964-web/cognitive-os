"""Cross-module source identity, callback ancestry and native repair boundaries."""
from copy import deepcopy
from pathlib import Path
import sys

import pytest

from runtime.native_failure_acceptance import _probe, run_native_acceptance
from runtime.narrow_type_evidence_binding import content_digest
from runtime.project_failure_evidence_packet import build_failure_evidence_packet
from runtime.project_native_failure_binding import _interpret_pytest_result
from runtime.repair_target_nomination import (
    trace_failure_methods, nomination_context, validate_nomination, _packet_contract,
)
from runtime.repair_trial_binding import build_repair_trial_packet, validate_repair_trial_source
from runtime.stage_finalization_workspace import inventory, snapshot
from runtime.upstream_llm_candidates import _replacement

SOURCES = ['api.py', 'callbacks.py', 'dispatch.py']


def prepare_functions(root, *, generator=True, body=None, substituted=False):
    project = root / 'project'
    (project / 'tests').mkdir(parents=True)
    (project / 'pytest.ini').write_text('[pytest]\n', encoding='utf-8')
    (project / 'pyproject.toml').write_text("[project]\nname='callback-library'\nversion='0.1.0'\n", encoding='utf-8')
    (project / 'api.py').write_text(
        'from dispatch import dispatch\nfrom callbacks import convert\n'
        'def render(value):\n    return dispatch(convert, value)\n', encoding='utf-8')
    (project / 'dispatch.py').write_text(
        'def dispatch(callback, value):\n    return ' +
        ("next(callback(value))\n" if generator else 'callback(value)\n'), encoding='utf-8')
    (project / 'callbacks.py').write_text(
        'def register(fn):\n    return fn\n@register\ndef convert(value):\n    ' +
        ('yield ' if generator else 'return ') + "'broken' if value == 'bad' else value\n"
        "def unrelated(value):\n    return 'unused'\n", encoding='utf-8')
    test = 'from api import render\n'
    if substituted:
        test += ("import api\napi.convert = eval(compile('lambda value: iter([value])', "
                 "api.convert.__code__.co_filename, 'eval'))\n")
    test += 'def test_case():\n' + (body or "    assert render('good') == 'good'\n    assert render('bad') == 'fixed'\n")
    test += "def test_preserved():\n    assert render('good') == 'good'\n"
    (project / 'tests/test_case.py').write_text(test, encoding='utf-8')
    records = []
    for i in range(2):
        probe = _probe(project, root / f'intake-{i}', ['tests/test_case.py::test_case'], [], 20, Path(sys.executable))
        output = Path(probe['output']).read_text(encoding='utf-8')
        records.append({**_interpret_pytest_result(project, probe['returncode'], output, {}), 'output': output})
    failure = {'target': 'api.py:render', 'failure_signature': records[0]['failure_signature'],
               'failing_nodeids': ['tests/test_case.py::test_case'], 'detail': records[0]['output'], 'failure_kind': 'test_failed'}
    packet = build_failure_evidence_packet(project_dir=project, failure=failure, chain_case={'repetitions': records})
    assert packet['status'] == 'complete', packet
    return project, packet


def bundle_for(project, packet, root):
    trace = trace_failure_methods(project=project, packet=packet, work_dir=root / 'trace',
                                  authorized=True, source_files=SOURCES)
    assert trace['status'] == 'observed_call_scope', trace
    context = nomination_context(project=project, packet=packet, trace=trace)
    payload = {'target': 'callbacks.py:convert', 'context_digest': context['context_digest'],
        'file_sha256': context['file_sha256_by_target']['callbacks.py:convert'],
        'reason': 'This callback runs under the observed API and contains the branch responsible for the mismatched value.'}
    nomination = validate_nomination(payload, project=project, packet=packet, trace=trace, context=context)
    return {'nomination': nomination, 'trace': trace, 'context': context}


@pytest.fixture(scope='module')
def function_evidence(tmp_path_factory):
    root = tmp_path_factory.mktemp('function-nomination')
    project, packet = prepare_functions(root)
    return project, packet, bundle_for(project, packet, root)


def test_generator_callback_is_bound_to_its_own_file(function_evidence, tmp_path):
    project, observation, bundle = function_evidence
    context = bundle['context']
    assert context['eligible_targets'] == ['callbacks.py:convert', 'dispatch.py:dispatch']
    assert context['call_edges'] == [['api.py:render', 'dispatch.py:dispatch'],
                                     ['dispatch.py:dispatch', 'callbacks.py:convert']]
    packet = build_repair_trial_packet(project=project, observation=observation, bundle=bundle)
    assert packet['target_source']['path'] == 'callbacks.py'
    assert packet['observation_packet'] == observation
    assert not bundle['nomination']['root_cause_proven']
    before = inventory(project)
    copy = tmp_path / 'patched'
    snapshot(project, copy, before)
    path = copy / 'callbacks.py'
    path.write_text(_replacement(path.read_text(), packet['target'],
        "def convert(value):\n    yield 'fixed' if value == 'bad' else value\n"), encoding='utf-8')
    accepted = run_native_acceptance(source_project=project, patched_project=copy,
        contract=_packet_contract(packet), work_dir=tmp_path / 'accept')
    assert accepted['status'] == 'passed', accepted
    assert '@register' in path.read_text()
    assert inventory(project) == before
    (copy / 'api.py').write_text((copy / 'api.py').read_text() + '\n# unauthorized\n')
    rejected = run_native_acceptance(source_project=project, patched_project=copy,
        contract=_packet_contract(packet), work_dir=tmp_path / 'reject')
    assert rejected['status'] == 'failed'
    assert not rejected['probes']


@pytest.mark.parametrize('mutation', ['unreached', 'wrong_hash', 'probe', 'disconnected', 'ambiguous'])
def test_forged_function_evidence_rejected(function_evidence, mutation):
    project, packet, bundle = function_evidence
    bundle = deepcopy(bundle)
    trace, context = bundle['trace'], bundle['context']
    payload = {k: bundle['nomination'][k] for k in ('context_digest', 'file_sha256', 'reason')}
    payload['target'] = bundle['nomination']['repair_target']
    if mutation == 'unreached':
        payload['target'] = 'callbacks.py:unrelated'
    elif mutation == 'wrong_hash':
        payload['file_sha256'] = packet['target_source']['file_sha256']
    else:
        if mutation == 'probe':
            trace['probe_hashes']['repair_function_catalog.py'] = '0' * 64
        else:
            for probe in trace['probes']:
                invocations = probe['trace']['rows'][0]['invocations']
                if mutation == 'disconnected':
                    invocations[0]['edges'] = []
                else:
                    invocations.append(deepcopy(invocations[0]))
        trace['trace_digest'] = content_digest({k: v for k, v in trace.items() if k != 'trace_digest'})
    with pytest.raises(ValueError):
        validate_nomination(payload, project=project, packet=packet, trace=trace, context=context)


def test_changed_callback_invalidates_trial(function_evidence, tmp_path):
    project, observation, bundle = function_evidence
    packet = build_repair_trial_packet(project=project, observation=observation, bundle=bundle)
    copy = tmp_path / 'changed'
    snapshot(project, copy, inventory(project))
    (copy / 'callbacks.py').write_text('def convert(value): return value\n')
    with pytest.raises(ValueError, match='stale_project_inventory'):
        validate_repair_trial_source(copy, packet)


def test_two_observed_calls_fail_closed(tmp_path):
    project, packet = prepare_functions(tmp_path, body="    assert render('bad') + render('bad') == 'fixed'\n")
    trace = trace_failure_methods(project=project, packet=packet, work_dir=tmp_path / 'trace',
                                  authorized=True, source_files=SOURCES)
    assert trace['status'] == 'blocked'


def test_runtime_substitution_cannot_impersonate_owned_callback(tmp_path):
    project, packet = prepare_functions(tmp_path, substituted=True)
    trace = trace_failure_methods(project=project, packet=packet, work_dir=tmp_path / 'trace',
                                  authorized=True, source_files=SOURCES)
    assert trace['status'] == 'blocked'
    invocation = trace['probes'][0]['trace']['rows'][0]['invocations'][0]
    assert invocation['unsupported_calls'][0]['reason'] == 'unrecognized_source_code'


@pytest.mark.parametrize('sources', [['../outside.py'], ['tests/test_case.py'], ['callbacks.py']])
def test_invalid_source_ownership_or_entrypoint(function_evidence, tmp_path, sources):
    project, packet, _ = function_evidence
    with pytest.raises(ValueError):
        trace_failure_methods(project=project, packet=packet, work_dir=tmp_path / 'trace',
                              authorized=True, source_files=sources)
    assert not (tmp_path / 'trace').exists()
