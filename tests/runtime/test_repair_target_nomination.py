"""Real subprocess evidence: fail closed outside one source-bound failing call."""
from copy import deepcopy
from pathlib import Path

import pytest

from runtime.native_failure_acceptance import _probe
from runtime.project_failure_evidence_packet import build_failure_evidence_packet
from runtime.project_native_failure_binding import _interpret_pytest_result
from runtime.repair_target_nomination import (
    trace_failure_methods, nomination_context, validate_nomination, nomination_messages,
)
from runtime.narrow_type_evidence_binding import content_digest
from runtime.stage_finalization_workspace import inventory

PRODUCTION = '''class Worker:
    def convert(self, value):
        return getattr(self, 'convert_' + value)()
    def convert_good(self):
        return 'good'
    def convert_bad(self):
        return 'broken'
    def unrelated(self):
        return 'unused'
'''


def prepare(root, *, body=None, production=PRODUCTION):
    project = root / 'project'
    (project / 'tests').mkdir(parents=True)
    (project / 'core.py').write_text(production, encoding='utf-8')
    (project / 'tests/__init__.py').write_text('', encoding='utf-8')
    (project / 'tests/utils.py').write_text(
        'from core import Worker\ndef render(value): return Worker().convert(value)\n', encoding='utf-8')
    body = body or "    assert render('good') == 'good'\n    assert render('bad') == 'fixed'\n"
    (project / 'tests/test_case.py').write_text('from .utils import render\ndef test_case():\n' + body, encoding='utf-8')
    (project / 'pytest.ini').write_text('[pytest]\n', encoding='utf-8')
    import sys
    records = []
    for i in range(2):
        probe = _probe(project, root / f'intake-{i}', ['tests/test_case.py::test_case'], [], 20, Path(sys.executable))
        output = Path(probe['output']).read_text(encoding='utf-8')
        record = _interpret_pytest_result(project, probe['returncode'], output, {})
        records.append({**record, 'output': output})
    first = records[0]
    failure = {'target': 'core.py:Worker.convert', 'failure_signature': first['failure_signature'],
        'failing_nodeids': ['tests/test_case.py::test_case'], 'detail': records[0]['output'], 'failure_kind': 'test_failed'}
    packet = build_failure_evidence_packet(project_dir=project, failure=failure, chain_case={'repetitions': records})
    assert packet['status'] == 'complete', packet
    return project, packet


@pytest.fixture(scope='module')
def evidence(tmp_path_factory):
    root = tmp_path_factory.mktemp('nomination')
    project, packet = prepare(root)
    before = inventory(project)
    trace = trace_failure_methods(project=project, packet=packet, work_dir=root / 'trace', authorized=True)
    assert trace['status'] == 'observed_call_scope', trace
    assert inventory(project) == before
    context = nomination_context(project=project, packet=packet, trace=trace)
    return project, packet, trace, context


def proposal(context, target='core.py:Worker.convert_bad'):
    return {'target': target, 'context_digest': context['context_digest'], 'file_sha256': context['file_sha256'],
        'reason': 'The selected internal method executes in the failing assertion and returns the mismatched result.'}


def test_actual_dynamic_dispatch_keeps_only_failing_assertion(evidence):
    project, packet, trace, context = evidence
    assert context['eligible_targets'] == ['core.py:Worker.convert_bad']
    assert context['call_edges'] == [['core.py:Worker.convert', 'core.py:Worker.convert_bad']]
    saved = deepcopy(packet)
    nomination = validate_nomination(proposal(context), project=project, packet=packet, trace=trace, context=context)
    assert packet == saved
    assert nomination['observed_target'] == packet['target']
    assert nomination['repair_target'] == 'core.py:Worker.convert_bad'
    assert nomination['execution_authorized'] is nomination['source_apply'] is nomination['root_cause_proven'] is False
    assert 'no execution authority' in nomination_messages(context)[0]['content']


@pytest.mark.parametrize('target', [
    'core.py:Worker.unrelated', 'core.py:Worker.convert_good', 'core.py:Worker.convert',
    'tests/utils.py:render', '../external.py:Worker.convert_bad', 'other.py:Worker.convert_bad',
])
def test_unrelated_passing_test_helper_entrypoint_and_external_targets_rejected(evidence, target):
    project, packet, trace, context = evidence
    with pytest.raises(ValueError, match='outside_observed_call_scope'):
        validate_nomination(proposal(context, target), project=project, packet=packet, trace=trace, context=context)


@pytest.mark.parametrize('field', ['context_digest', 'file_sha256'])
def test_model_cannot_change_bound_hash(evidence, field):
    project, packet, trace, context = evidence
    payload = proposal(context)
    payload[field] = '0' * 64
    with pytest.raises(ValueError, match='source_binding_mismatch'):
        validate_nomination(payload, project=project, packet=packet, trace=trace, context=context)


def test_model_cannot_add_execution_authority_or_patch(evidence):
    project, packet, trace, context = evidence
    payload = {**proposal(context), 'execution_authorized': True, 'replacement_source': 'patch'}
    with pytest.raises(ValueError, match='response_schema'):
        validate_nomination(payload, project=project, packet=packet, trace=trace, context=context)


def test_source_and_context_revalidated(evidence, tmp_path):
    project, packet, trace, context = evidence
    changed = deepcopy(context)
    changed['eligible_targets'].append('core.py:Worker.unrelated')
    with pytest.raises(ValueError, match='context_changed'):
        validate_nomination(proposal(changed), project=project, packet=packet, trace=trace, context=changed)
    from runtime.stage_finalization_workspace import snapshot
    copy = tmp_path / 'changed'
    snapshot(project, copy, inventory(project))
    with (copy / 'core.py').open('a', encoding='utf-8') as stream:
        stream.write('\n# changed\n')
    with pytest.raises(ValueError, match='stale_project_inventory'):
        validate_nomination(proposal(context), project=copy, packet=packet, trace=trace, context=context)


@pytest.mark.parametrize('mutation', ['digest', 'unstable', 'disconnected'])
def test_trace_integrity_repeatability_and_call_path(evidence, mutation):
    project, packet, trace, context = evidence
    changed = deepcopy(trace)
    if mutation == 'digest':
        changed['observed_target'] = 'core.py:Worker.unrelated'
    elif mutation == 'unstable':
        changed['probes'][0]['trace']['rows'][0]['failure_line'] += 1
    else:
        for probe in changed['probes']:
            probe['trace']['rows'][0]['invocations'][0]['edges'] = []
    if mutation != 'digest':
        changed['trace_digest'] = content_digest({k: v for k, v in changed.items() if k != 'trace_digest'})
    with pytest.raises(ValueError):
        nomination_context(project=project, packet=packet, trace=changed)


def test_two_calls_in_failing_assertion_are_ambiguous(tmp_path):
    project, packet = prepare(tmp_path, body="    assert render('bad') + render('bad') == 'fixed'\n")
    trace = trace_failure_methods(project=project, packet=packet, work_dir=tmp_path / 'trace', authorized=True)
    assert trace['status'] == 'blocked'
    assert trace['probes'][0]['trace']['rows'][0]['supported'] is False


def test_runtime_method_substitution_is_not_source_evidence(tmp_path):
    production = PRODUCTION.replace("return getattr(self, 'convert_' + value)()",
        "self.convert_bad = lambda: 'broken'\n        return getattr(self, 'convert_' + value)()")
    # Build the observation before runtime mutation is added, then create a
    # source-current packet explicitly for the trace boundary under test.
    project, packet = prepare(tmp_path)
    (project / 'core.py').write_text(production, encoding='utf-8')
    from runtime.project_failure_evidence_packet import _target_source, evidence_packet_digest
    packet['project_inventory_digest'] = content_digest(inventory(project))
    packet['target_source'] = _target_source(project, packet['target'])
    packet['packet_digest'] = evidence_packet_digest(packet)
    with pytest.raises(ValueError, match='method_attribute_mutated'):
        trace_failure_methods(project=project, packet=packet, work_dir=tmp_path / 'trace', authorized=True)


def test_trace_requires_authorization_before_execution(evidence, tmp_path):
    project, packet, _, _ = evidence
    with pytest.raises(ValueError, match='authorization_required'):
        trace_failure_methods(project=project, packet=packet, work_dir=tmp_path / 'trace')
    assert not (tmp_path / 'trace').exists()


def test_nested_helpers_and_source_compiled_dispatch_are_supported(tmp_path):
    production = PRODUCTION.replace("return getattr(self, 'convert_' + value)()",
        "def name():\n            return helper('convert_' + value)\n"
        "        dispatch = lambda: getattr(self, name())()\n        return dispatch()")
    production += '\ndef helper(value): return value\n'
    project, packet = prepare(tmp_path, production=production)
    trace = trace_failure_methods(project=project, packet=packet, work_dir=tmp_path / 'trace', authorized=True)
    assert trace['status'] == 'observed_call_scope', trace
    context = nomination_context(project=project, packet=packet, trace=trace)
    assert context['eligible_targets'] == ['core.py:Worker.convert_bad']


@pytest.mark.parametrize('source', [
    'class Worker(Base):\n    def convert(self, v): return v\n',
    'class Worker:\n    @property\n    def convert(self): return 1\n',
    'class Worker:\n    async def convert(self, v): return v\n',
    'class Worker:\n    def convert(self, v): yield v\n',
    'class Worker:\n    def convert(self, v): return v\n    def convert(self, v): return v\n',
    'class Worker:\n    def convert(self, v): return v\nsetattr(Worker, "other", lambda: None)\n',
])
def test_unsupported_method_catalog_fails_closed(source):
    from runtime.repair_target_trace_probe import method_catalog
    with pytest.raises(ValueError):
        method_catalog(source, 'core.py:Worker.convert')


def test_changed_probe_invalidates_trace(evidence):
    project, packet, trace, _ = evidence
    changed = deepcopy(trace)
    changed['probe_source_sha256'] = '0' * 64
    changed['trace_digest'] = content_digest({k: v for k, v in changed.items() if k != 'trace_digest'})
    with pytest.raises(ValueError, match='invalid_or_stale_trace'):
        nomination_context(project=project, packet=packet, trace=changed)
