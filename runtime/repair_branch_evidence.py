"""Line events constrain reached-return claims, without certifying root cause."""
import ast
import hashlib
from pathlib import Path

from .narrow_type_evidence_binding import content_digest
from .repair_trial_binding import observed_packet, validate_repair_trial_source
from .repair_target_nomination import trace_failure_methods, nomination_context
from .stage_finalization_workspace import owned_path


def collect_branch_evidence(*, project, packet, work_dir, authorized=False, python_executable=None):
    validate_repair_trial_source(project, packet)
    trace = trace_failure_methods(project=project, packet=observed_packet(packet), work_dir=work_dir,
        authorized=authorized, python_executable=python_executable, line_target=packet['target'])
    return branch_evidence(project=project, packet=packet, trace=trace)


def branch_evidence(*, project, packet, trace):
    validate_repair_trial_source(project, packet)
    nomination_context(project=project, packet=observed_packet(packet), trace=trace)
    if (trace.get('line_target') != packet['target'] or trace.get('branch_probe_sha256') !=
            hashlib.sha256(Path(__file__).with_name('repair_branch_trace_probe.py').read_bytes()).hexdigest()):
        raise ValueError('invalid_branch_probe_binding')
    invocation = trace['probes'][0]['trace']['rows'][0]['invocations'][0]
    events = invocation.get('repair_line_events', [])
    if (not events or len(events) > 256 or any(e not in {'line', 'return'} or type(n) is not int for e, n in events)):
        raise ValueError('bounded_normal_line_trace_required')
    path, _, symbol = packet['target'].partition(':')
    source = owned_path(project, path).read_text(encoding='utf-8')
    tree = ast.parse(source)
    scope = tree.body
    for part in symbol.split('.'):
        nodes = [n for n in scope if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name == part]
        if len(nodes) != 1:
            raise ValueError('unique_branch_source_required')
        function = nodes[0]
        scope = function.body
    lines = {n for e, n in events if e == 'line'}
    returned = {n for e, n in events if e == 'return'}
    if any(n < function.lineno or n > function.end_lineno for _, n in events):
        raise ValueError('line_outside_repair_method')
    # Restrict to explicit returns on executed lines. Exceptions, generators and
    # implicit returns remain unsupported; no inferred runtime values are stored.
    returns = [n for n in ast.walk(function) if isinstance(n, ast.Return) and n.lineno in returned & lines]
    if not returns or any(n not in {r.lineno for r in returns} for n in returned):
        raise ValueError('explicit_reached_return_required')
    facts = [{'id': f'R{i}', 'line': n.lineno, 'source': ast.get_source_segment(source, n)}
             for i, n in enumerate(sorted(returns, key=lambda n: n.lineno), 1)]
    result = {'schema_version': 'repair_branch_evidence.v1', 'packet_digest': packet['packet_digest'],
        'target': packet['target'], 'file_sha256': packet['target_source']['file_sha256'],
        'trace': trace, 'facts': facts, 'executed_lines': sorted(lines), 'execution_authorized': False,
        'limitations': 'Reached source lines/returns only; no captured values, unique-root-cause or universal branch claim.'}
    result['branch_digest'] = content_digest(result)
    return result


def validate_branch_evidence(project, packet, evidence):
    if branch_evidence(project=project, packet=packet, trace=evidence['trace']) != evidence:
        raise ValueError('branch_evidence_changed')
