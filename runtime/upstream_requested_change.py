"""Bridge explicit requirements to the existing bounded native repair workflow."""
from copy import deepcopy
from pathlib import Path

from .narrow_type_evidence_binding import content_digest
from .stage_finalization_workspace import inventory, owned_path
from .upstream_change_impact import analyze_change_impact
from .upstream_requested_acceptance import requested_test_bindings, verify_requested_acceptance


def prepare_requested_change(report: dict, project: Path) -> dict:
    contract = deepcopy(report['task_contract'])
    result = {'contract': contract, 'analysis': deepcopy(report['task_analysis']),
              'status': 'needs_clarification', 'execution_authorized': False}
    try:
        if contract['change_kind'] != 'defect' or report['task_analysis']['status'] != 'source_bound':
            raise ValueError('source_bound_defect_request_required')
        result['bindings'] = requested_test_bindings(contract, inventory(project))
        targets = list(dict.fromkeys(t for r in contract['requirements'] for t in r.get('targets', [])))
        if len(targets) != 1:
            raise ValueError('single_native_repair_target_required')
        result['impact'] = analyze_change_impact(project, targets)
        result['status'] = 'ready_for_candidate_check'
    except (ValueError, OSError, SyntaxError, UnicodeError) as exc:
        result['reason'] = str(exc)
    return result


def bind_requested_change(diagnosis: dict, request: dict, *, project: Path, root: Path) -> dict:
    root = root.resolve()
    result = deepcopy(diagnosis)
    for issue in result.get('issues', []):
        if not issue.get('failure_specific_reducer_required'):
            continue
        row = deepcopy(request)
        try:
            if row['status'] != 'ready_for_candidate_check':
                raise ValueError(row.get('reason', 'request_not_ready'))
            comparison = issue.get('causal_comparison') or {}
            if comparison.get('status') != 'selected_for_regression':
                raise ValueError('unique_supported_candidate_required')
            if row['impact']['targets'] != [comparison.get('target')]:
                raise ValueError('request_and_failure_target_mismatch')
            selected = next(r for r in comparison['attempts'] if r['id'] == comparison['selected_candidate_id'])
            model = comparison.get('candidate_origin') == 'llm_structured_proposal'
            if model:
                from .upstream_model_requirements import requested_model_copy
                patched = requested_model_copy(issue, row, project=project, root=root)
            else:
                patched = owned_path(root, Path(selected['patched_project']).relative_to(root).as_posix())
            proof = verify_requested_acceptance(project=project,
                patched=patched, contract=row['contract'],
                impact=row['impact'], work_dir=root / 'artifacts/requested_acceptance',
                native_replay_settings=(issue.get('failure_evidence_packet') or {}).get('observation_packet',
                    issue.get('failure_evidence_packet') or {}).get('native_replay_settings'))
            row['acceptance'] = proof
            if (proof['status'] != 'passed' or proof['source_inventory_digest'] != comparison['source_inventory_digest']
                    or proof['patched_inventory_digest']
                    != selected['evidence']['patched_inventory_digest']):
                raise ValueError('requested_behavior_not_verified')
            row.update(status='verified_for_regression', execution_authorized=True,
                       execution_scope='explicit_model_candidate_sandbox_only' if model else 'existing_explicit_training_sandbox_only')
        except (ValueError, OSError, KeyError, StopIteration, SyntaxError, UnicodeError) as exc:
            row.update(status='needs_clarification', execution_authorized=False, reason=str(exc))
            issue['allowed_operator_ids'] = []
            issue.pop('training_replay_authority', None)
            issue.pop('llm_training_replay', None)
            issue.pop('model_delivery', None)
            issue.setdefault('repair_design', {}).update(status='proposal_review_required', execution_authority=False)
            if str(exc) != 'unique_supported_candidate_required' or not issue.get('causal_feedback'):
                issue['causal_feedback'] = {'role': 'spec_writer' if str(exc) == 'requested_behavior_not_verified' else 'analyzer',
                                          'next_action': 'revise_requested_behavior_or_acceptance',
                                          'reason': str(exc), 'automatic_retry': False}
        row['request_digest'] = content_digest(row)
        if row['execution_authorized'] and issue.get('model_delivery'):
            from .upstream_model_requirements import bind_model_request_ticket
            bind_model_request_ticket(issue, row)
        issue['requested_change'] = row
    return result


def bind_requested_spec(spec: dict, issue: dict) -> dict:
    request = issue.get('requested_change')
    if request is None:
        return spec
    row = deepcopy(spec)
    contract = request['contract']
    row['task_contract'] = deepcopy(contract)
    row['requested_change'] = deepcopy(request)
    row['requirements'] = [*[{**deepcopy(r), 'priority': 'MUST', 'source': 'task_contract',
                             'origin': contract['origin'],
                             **({'target':r['targets'][0]} if len(r.get('targets', [])) == 1 else {})}
                            for r in contract['requirements']], *row['requirements']]
    criteria = []
    offsets = {}
    for index, binding in enumerate(request.get('bindings', []) if request.get('impact') else [], 1):
        requirement = next(r for r in contract['requirements'] if r['id'] == binding['requirement_id'])
        ident = f'AC-REQUEST-NATIVE-{index:03d}'
        target = request['impact']['targets'][0]
        offset = offsets.get(requirement['id'], 0)
        example = requirement['acceptance_examples'][offset]
        offsets[requirement['id']] = offset + 1
        criteria.append({'id': ident, 'requirement_id': requirement['id'], 'source': target,
                         'criterion': requirement['statement'], 'verification': f"pytest {binding['nodeid']}",
                         'example': deepcopy(example), 'origin': contract['origin'],
                         'execution_status': 'passed' if request['execution_authorized'] else 'not_verified'})
        row['traceability_table'].append({'requirement_id': requirement['id'], 'requirement': requirement['statement'],
                                        'source': target, 'acceptance_id': ident, 'target': target})
    row['acceptance_criteria'] = [*row['acceptance_criteria'], *criteria]
    row['requested_acceptance_criteria'] = deepcopy(criteria)
    row['requirement_traceability'] = [{'requirement_id': r['id'], 'targets': r.get('targets', []),
        'acceptance_ids': [c['id'] for c in criteria if c['requirement_id'] == r['id']]}
        for r in contract['requirements']]
    row['task_handoff'] = {'status': request['status'], 'execution_authorized': request['execution_authorized'],
                           'contract_digest': contract['contract_digest'],
                           'gaps': [] if request['execution_authorized'] else [{'reason': request.get('reason')} ]}
    row.setdefault('reasoning_provenance', {})['acceptance'] = (
        'caller_supplied_native_tests_executed_on_baseline_and_candidate; semantic_adequacy_not_independently_verified'
        if request['execution_authorized'] else 'caller_supplied_native_tests; requested_behavior_not_verified')
    if not request['execution_authorized']:
        row['implementation_delta']['status'] = 'blocked'
        row['implementation_handoff']['mode'] = 'blocked'
    return row
