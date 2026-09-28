"""Bound one diagnosis retry to actual contradictory native results."""
from pathlib import Path
from copy import deepcopy

from .narrow_type_evidence_binding import content_digest
from .stage_finalization_workspace import inventory
from .project_native_failure_binding import _interpret_pytest_result


def native_counterexamples(project, packet, comparison):
    from .repair_trial_binding import validate_repair_trial_source
    validate_repair_trial_source(project, packet)
    if (comparison.get('status') != 'no_supported_candidate'
            or comparison.get('candidate_origin') != 'llm_structured_proposal'
            or comparison.get('packet_digest') != packet['packet_digest']
            or comparison.get('source_inventory_digest') != content_digest(inventory(project))
            or comparison.get('comparison_digest') != content_digest({k:v for k,v in comparison.items() if k!='comparison_digest'})):
        raise ValueError('invalid_counterexample_comparison')
    rows = []
    for attempt in comparison.get('attempts', []):
        evidence = attempt.get('evidence') or {}
        checks = evidence.get('summary', {}).get('native_replay_checks', {})
        required = ('source_packet_current', 'patch_scope_preserved', 'baseline_failure_repeated',
            'recorded_failure_reproduced', 'test_collection_preserved', 'source_copies_unchanged', 'input_projects_unchanged')
        probes = evidence.get('probes') or []
        if (attempt.get('outcome') != 'contradicted_by_targeted_tests' or len(probes) != 3
                or not all(checks.get(k) is True for k in required) or checks.get('patched_tests_passed') is not False
                or any(p.get('intake_signature') != packet['failure_signature'] for p in probes[:2])):
            raise ValueError('repeated_native_counterexample_required')
        patched = Path(attempt['patched_project']).resolve()
        if (patched == project.resolve() or evidence.get('patched_inventory_digest') != content_digest(inventory(patched))):
            raise ValueError('counterexample_patch_changed')
        from .upstream_llm_candidates import validate_model_candidate
        from .stage_finalization_workspace import owned_path
        path = packet['target'].partition(':')[0]
        validate_model_candidate({**attempt, 'replacement_source': owned_path(patched, path).read_bytes().decode('utf-8')},
            packet, owned_path(project, path).read_bytes().decode('utf-8'))
        output_path = Path(probes[-1]['output']).resolve()
        if output_path.name != 'output.txt' or not output_path.is_relative_to(Path(evidence['result_path']).resolve().parent):
            raise ValueError('counterexample_output_not_owned')
        output = output_path.read_text(encoding='utf-8')
        parsed = _interpret_pytest_result(patched, probes[-1]['returncode'], output, {})
        if probes[-1]['returncode'] != 1 or parsed.get('failure_signature') != probes[-1].get('intake_signature'):
            raise ValueError('counterexample_output_identity_mismatch')
        rows.append({'candidate_id': attempt['id'], 'replacement_digest': attempt['replacement_digest'],
            'replacement_function': attempt['provenance']['replacement_function'], **feedback_output(output)})
        if attempt['provenance'].get('related_replacements'):
            rows[-1]['related_replacements']=deepcopy(attempt['provenance']['related_replacements'])
    if not 1 <= len(rows) <= 4:
        raise ValueError('bounded_counterexample_set_required')
    result = {'schema_version': 'repair_counterexamples.v1', 'comparison_digest': comparison['comparison_digest'],
        'packet_digest': packet['packet_digest'], 'examples': rows, 'execution_authorized': False}
    result['feedback_digest'] = content_digest(result)
    return result


def feedback_output(output):
    if len(output) <= 6000:
        return {'native_output': output, 'output_digest': content_digest(output)}
    # Full output is validated above and retained at the probe receipt. Explicit
    # suffix metadata prevents a bounded diagnostic from masquerading as full output.
    suffix = output[-2000:]
    return {'native_output': suffix, 'output_digest': content_digest(suffix),
        'output_excerpt': {'kind': 'exact_suffix', 'start_char': len(output) - len(suffix),
            'end_char': len(output), 'full_output_digest': content_digest(output),
            'omitted_prefix': True, 'limitations': 'Diagnostic excerpt only; full output retained in native probe receipt.'}}


def bind_saved_counterexample(diagnosis, project, comparison):
    result = deepcopy(diagnosis)
    issues = [i for i in result.get('issues', []) if i.get('failure_specific_reducer_required')]
    if len(issues) != 1:
        raise ValueError('single_counterexample_issue_required')
    issue = issues[0]
    feedback = native_counterexamples(project, issue['failure_evidence_packet'], comparison)
    issue['prior_native_comparison'] = deepcopy(comparison)
    issue['native_counterexamples'] = feedback
    issue['saved_counterexample_origin'] = {'comparison_digest': comparison['comparison_digest'],
        'scope': 'prior consumed development; revalidated before new model calls'}
    return result
