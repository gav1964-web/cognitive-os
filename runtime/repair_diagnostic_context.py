"""Bound optional observations and accumulated contradictions to model input."""
from copy import deepcopy
import ast

from .narrow_type_evidence_binding import content_digest
from .repair_counterexamples import native_counterexamples
from .repair_observations import validate_repair_observations, observation_context


def bind_diagnostic_context(diagnosis, project, *, observations=None, history=None):
    result = deepcopy(diagnosis)
    issues = [i for i in result.get('issues', []) if i.get('failure_specific_reducer_required')]
    if len(issues) != 1:
        raise ValueError('single_diagnostic_issue_required')
    issue = issues[0]
    if observations is not None:
        validate_repair_observations(project, issue['failure_evidence_packet'], observations)
        issue['repair_observations'] = deepcopy(observations)
    if history is not None:
        if not isinstance(history, list) or not 1 <= len(history) <= 3:
            raise ValueError('one_to_three_prior_comparisons_required')
        if len({c['comparison_digest'] for c in history}) != len(history):
            raise ValueError('duplicate_counterexample_history')
        for comparison in history:
            native_counterexamples(project, issue['failure_evidence_packet'], comparison)
        issue['repair_counterexample_history'] = deepcopy(history)
    diagnostic_context(issue, project)
    return result


def diagnostic_context(issue, project):
    result = {}
    if (issue.get('repair_observations') is None and issue.get('repair_counterexample_history') is None
            and issue.get('source_dependency_context') is None and issue.get('candidate_validation_feedback') is None):
        return result
    packet = issue['failure_evidence_packet']
    if issue.get('candidate_validation_feedback') is not None:
        from .candidate_rejection_feedback import rejection_feedback
        result['candidate_validation_rejection']=rejection_feedback(project,packet,issue['candidate_validation_feedback'])
    if issue.get('source_dependency_context') is not None:
        from .upstream_dependency_context import dependency_context
        current = dependency_context(project,packet['target'])
        if current != issue['source_dependency_context']:
            raise ValueError('source_dependency_context_changed')
        result['source_dependencies'] = current
    if issue.get('repair_observations') is not None:
        validate_repair_observations(project, packet, issue['repair_observations'])
        key = ('native_test_observations' if issue['repair_observations'].get('schema_version') in
               {'native_repair_observations.v1', 'native_repair_observations.v2'} else 'isolated_assertion_observations')
        result[key] = observation_context(issue['repair_observations'], compact=True)
    if issue.get('repair_counterexample_history') is not None:
        history = issue['repair_counterexample_history']
        if not 1 <= len(history) <= 3 or len({c['comparison_digest'] for c in history}) != len(history):
            raise ValueError('bounded_distinct_counterexamples_required')
        rows = []
        for comparison in history:
            feedback = native_counterexamples(project, packet, comparison)
            for example in feedback['examples']:
                output = example['native_output']
                rows.append({'comparison_digest': comparison['comparison_digest'],
                    'feedback_digest': feedback['feedback_digest'], 'candidate_id': example['candidate_id'],
                    'replacement_function': example['replacement_function'],
                    'native_diagnostic_suffix': output[-600:],
                    'full_output_digest': example.get('output_excerpt', {}).get('full_output_digest', example['output_digest']),
                    'excerpt_notice': 'Exact diagnostic suffix only; full validated native output retained in comparison receipt.'})
        result['counterexample_history'] = rows
    if result:
        result['authority'] = 'source_bound_diagnostic_input_only; native acceptance unchanged'
        result['context_digest'] = content_digest(result)
    return result


def enrich_diagnostic_envelope(envelope, issue, project):
    context = diagnostic_context(issue, project)
    if not context:
        return
    envelope['diagnostic_context'] = context
    calls = envelope.get('repair_call_context')
    if calls:
        # Same projection for both comparison arms: retain target, observed API,
        # and direct callers; every other method keeps its code identity/locations.
        shown = {envelope['target'], envelope['observed_target']}
        shown.update(a for a, b in calls['call_edges'] if b == envelope['target'])
        callees = {b for a, b in calls['call_edges'] if a == envelope['target']}
        for method in calls['methods']:
            if method['target'] not in shown:
                if method['target'] in callees and method.get('source'):
                    # Keep the source interface even when omitting its body. Parameter
                    # and return types constrain how the target consumes container data.
                    text = method['source']
                    function = ast.parse(text).body[0]
                    body = function.body[0]
                    lines = text.splitlines()
                    # AST columns are UTF-8 byte offsets, including one-line defs.
                    prefix = lines[body.lineno - 1].encode('utf-8')[:body.col_offset].decode('utf-8')
                    method['source_interface'] = '\n'.join([*lines[:body.lineno - 1], prefix]).rstrip()
                    method['interface_only'] = True
                method.pop('source', None)
        calls['source_projection'] = {'body_targets': sorted(shown),
            'interface_targets': sorted(callees - shown),
            'limitations': 'Other method bodies omitted; direct callee interfaces retained. Annotations are source declarations, not runtime type proof. Full bound context remains in the packet.'}
