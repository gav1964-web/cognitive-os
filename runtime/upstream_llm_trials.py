"""Connect advisory diagnosis to native trials and explicitly requested delivery."""
import json
import uuid
from copy import deepcopy
from pathlib import Path

from .local_inference import LocalInferenceError, call_json_chat
from .native_failure_acceptance import build_native_acceptance, preflight_native_acceptance, _validate
from .project_development_llm_hypothesis import build_llm_failure_hypothesis
from .stage_finalization_workspace import inventory, owned_path
from .upstream_causal_trials import compare_causal_candidates
from .upstream_llm_candidates import candidate_messages, build_model_candidates
from .upstream_candidate_context import candidate_source_context


def validate_llm_diagnosis_proposals(diagnosis: dict, *, project: Path, root: Path,
                                    config, authorized: bool = False,
                                    delivery_authorized: bool = False, request: dict | None = None,
                                    format_retries: int = 0, semantic_retries: int = 0,
                                    require_assertion_plan: bool | str = False, proposal_route: str = 'hypothesis', chat=None,
                                    include_dependency_context: bool = False,
                                    same_class_repairs: bool = False) -> dict:
    """Two calls; optional format correction and one native-feedback cycle.

Both enabled permit at most five logical calls: hypothesis, candidate,
format correction, revised hypothesis, revised candidate. Recursive retries
disable both budgets; the injected chat independently enforces token limits.

The configured inference client's existing transport failover still applies.
Replay uses trusted-code subprocess copies, not an OS security sandbox.
"""
    if not authorized:
        raise ValueError('explicit_training_trial_authorization_required')
    if config is None:
        raise ValueError('explicit_model_config_required')
    if type(include_dependency_context) is not bool:
        raise ValueError('dependency_context_policy_must_be_boolean')
    if type(same_class_repairs) is not bool or same_class_repairs and (not include_dependency_context or proposal_route!='hypothesis'):
        raise ValueError('same_class_repairs_require_dependency_context')
    if proposal_route not in {'hypothesis', 'direct'}:
        raise ValueError('invalid_model_proposal_route')
    if type(require_assertion_plan) is not bool and require_assertion_plan != 'when_supported':
        raise ValueError('assertion_plan_policy_must_be_boolean')
    if type(format_retries) is not int or format_retries not in (0, 1):
        raise ValueError('format_retry_budget_must_be_zero_or_one')
    if type(semantic_retries) is not int or semantic_retries not in (0, 1):
        raise ValueError('native_retry_requires_zero_or_one')
    result = deepcopy(diagnosis)
    retried = False
    issues = [r for r in result.get('issues', []) if r.get('failure_specific_reducer_required')]
    for issue in issues:
        issue['allowed_operator_ids'] = []
        issue['proposed_operator_ids'] = []
        for key in ('training_replay_authority', 'llm_training_replay', 'causal_hypothesis',
                    'llm_hypothesis_advisory', 'llm_candidate_trial', 'causal_comparison', 'causal_feedback'):
            issue.pop(key, None)
        issue.pop('model_delivery', None)
        issue.pop('requested_task_contract', None)
        issue['repair_design'] = {'status': 'proposal_review_required', 'execution_authority': False}
        comparison = {'status': 'not_compared', 'source_apply': False}
        trial = {'schema_version': 'upstream_llm_trial.v1', 'status': 'preflight',
            'proposal_route': proposal_route,
            'logical_model_calls': 0, 'automatic_retry': False,
            'format_retry_limit': format_retries, 'candidate_response_attempts': [],
            'source_apply': False, 'promotion_allowed': False,
            'native_trial_authorized': True, 'delivery_authorized': False,
            'configured_model': config.model,
            'model_origin': 'configured_inference_client; not independently attested',
            'usage_evidence': 'consult inference telemetry; unknown is not zero'}
        receipt = None
        try:
            if len(issues) != 1:
                raise ValueError('single_failure_issue_required')
            packet = issue.get('failure_evidence_packet') or {}
            target = packet.get('target', '')
            spec = {'contract_mode': 'failure_repair',
                'implementation_delta': {'intent': {'failure_evidence_packet': packet}},
                'acceptance_criteria': [{'id': f'AC-FAILURE-REPLAY-{i:03d}'}
                    for i, _ in enumerate(packet.get('failing_nodeids', []), 1)]}
            native_contract = build_native_acceptance(spec, target)
            _validate(native_contract, inventory(project))
            from .repair_trial_binding import observed_packet, validate_repair_trial_source
            validate_repair_trial_source(project, packet)
            if issue.get('preservation_evidence') is not None:
                from .repair_preservation import validate_preservation
                if proposal_route != 'hypothesis':
                    raise ValueError('preservation_requires_explicit_hypothesis_design')
                validate_preservation(packet, issue['preservation_evidence'], project)
            if include_dependency_context:
                from .upstream_dependency_context import dependency_context
                issue['source_dependency_context'] = dependency_context(project,target)
            if require_assertion_plan:
                from .repair_assertion_contract import build_assertion_contract
                try:
                    issue['assertion_contract'] = build_assertion_contract(packet)
                except ValueError as exc:
                    if require_assertion_plan != 'when_supported' or str(exc) not in {
                            'only_direct_test_assertions_supported', 'single_test_function_required',
                            'assertion_contract_budget_exceeded'}:
                        raise
                    trial['assertion_planning'] = {'status':'unsupported','reason':str(exc),
                        'fallback':'original source-bound native tests and full regression; no assertion-plan credit'}
                else:
                    trial['assertion_planning'] = {'status':'required','contract_digest':issue['assertion_contract']['contract_digest']}
            if issue.get('native_counterexamples') is not None:
                from .repair_counterexamples import native_counterexamples
                if native_counterexamples(project, packet, issue['prior_native_comparison']) != issue['native_counterexamples']:
                    raise ValueError('native_counterexamples_changed')
            if issue.get('affected_targets') != [target]:
                raise ValueError('model_trial_target_mismatch')
            if request is not None:
                from .upstream_model_requirements import model_request_context
                issue['requested_task_contract'] = model_request_context(request, project, target)
            failures = issue.get('failure_evidence') or []
            if (len(failures) != 1 or failures[0].get('target') != observed_packet(packet)['target']
                    or failures[0].get('failure_signature') != packet['failure_signature']
                    or failures[0].get('failing_nodeids') != packet['failing_nodeids']):
                raise ValueError('model_trial_failure_mismatch')
            source = owned_path(project, target.partition(':')[0]).read_bytes().decode('utf-8')
            if same_class_repairs:
                from .model_edit_scope import same_class_edit_scope
                issue['model_edit_scope'] = same_class_edit_scope(source,target)
            candidate_source_context(source, target)
            work = root.resolve() / 'artifacts/llm_causal_trials' / ('trial-' + uuid.uuid4().hex[:10])
            if project.resolve().is_relative_to(work) or work.is_relative_to(project.resolve()):
                raise ValueError('trial_output_must_be_outside_source_project')
            work.mkdir(parents=True, exist_ok=False)
            receipt = work / 'trial.json'
            trial['native_preflight'] = preflight_native_acceptance(
                source_project=project, contract=native_contract, work_dir=work)
            _persist(receipt, trial)
            if trial['native_preflight']['status'] != 'passed':
                raise ValueError('native_preflight:' + trial['native_preflight']['reason'])
            trial['packet_digest'] = packet['packet_digest']
            trial['status'] = 'source_obligations_preparing' if proposal_route == 'direct' else 'hypothesis_requested'
            trial['logical_model_calls'] = 0 if proposal_route == 'direct' else 1
            _persist(receipt, trial)
            if proposal_route == 'direct':
                from .upstream_direct_proposals import direct_candidate_messages
                messages, advisory = direct_candidate_messages(issue, project)
                trial['logical_model_calls'] = 0
                advisory.update(status='direct_source_obligations', model_invoked=False)
            else:
                advisory = build_llm_failure_hypothesis(issue=issue, project_dir=project, config=config,
                    **({'chat':chat} if chat is not None else {}))
            if advisory.get('model_invoked') is False:
                trial['logical_model_calls'] = 0
            if proposal_route == 'hypothesis':
                issue['llm_hypothesis_advisory'] = advisory
                trial['hypothesis_advisory'] = advisory
            else:
                trial['source_obligations'] = advisory
            if advisory['status'] not in {'accepted_hypothesis_only', 'direct_source_obligations'}:
                raise ValueError('model_hypothesis_' + advisory['status'] + ':' + ';'.join(advisory.get('errors', [])))
            if proposal_route == 'hypothesis':
                issue['causal_hypothesis'] = deepcopy(advisory['causal_hypothesis'])
            issue['repair_design'] = deepcopy(advisory['repair_design'])
            if proposal_route == 'hypothesis':
                messages = candidate_messages(packet, advisory, source)
            for attempt in range(format_retries + 1):
                trial['status'] = 'candidates_requested'
                trial['logical_model_calls'] += 1
                _persist(receipt, trial)
                payload = (chat or call_json_chat)(messages, config=config)
                encoded = json.dumps(payload, ensure_ascii=False)
                trial['candidate_response'] = payload if len(encoded) <= 40000 else {'error': 'response_budget_exceeded'}
                record = {'attempt': attempt + 1, 'response': trial['candidate_response']}
                trial['candidate_response_attempts'].append(record)
                _persist(receipt, trial)
                try:
                    if proposal_route == 'direct' and (not isinstance(payload, dict)
                            or not isinstance(payload.get('candidates'), list) or len(payload['candidates']) != 1):
                        raise ValueError('one_direct_candidate_required')
                    candidates = build_model_candidates(payload, packet=packet, advisory=advisory, source=source)
                except ValueError as exc:
                    record['validation_error'] = str(exc)
                    _persist(receipt, trial)
                    if (attempt == format_retries or str(exc) not in {
                            'candidate_response_schema', 'candidate_row_schema', 'replacement_must_be_single_function',
                            'replacement_removes_or_changes_doctests', 'replacement_source_syntax_error'}
                            or len(encoded) > 40000):
                        raise
                    from .model_candidate_feedback import format_feedback
                    messages = format_feedback(messages, payload, str(exc))
                    trial['automatic_retry'] = True
                else:
                    record['validation_status'] = 'accepted_for_native_comparison'
                    _persist(receipt, trial)
                    break
            comparison = compare_causal_candidates(project=project, packet=packet, candidates=candidates,
                work_dir=work / 'comparison', authorized=True, candidate_origin='llm_structured_proposal')
            trial['status'] = ('supported_hypothesis_review_required'
                if comparison['status'] == 'selected_for_regression' else comparison['status'])
        except (LocalInferenceError, ValueError, OSError, KeyError, TypeError, SyntaxError) as exc:
            trial.update(status='not_compared', reason=str(exc)[:240])
            comparison = {'status': 'not_compared', 'reason': str(exc)[:240], 'source_apply': False}
        issue['causal_comparison'] = comparison
        issue['repair_design'].update(execution_authority=False, source_apply=False, promotion_allowed=False)
        supported = comparison.get('status') == 'selected_for_regression'
        if supported and delivery_authorized:
            from .upstream_model_delivery import bind_model_delivery, AUTHORITY
            try:
                issue['model_delivery'] = bind_model_delivery(project=project, issue=issue, candidates=candidates)
                issue['repair_design'].update(status='model_candidate_replay_ready', execution_authority=AUTHORITY)
                trial.update(status='model_candidate_replay_ready', delivery_authorized=True,
                             model_delivery=issue['model_delivery'])
                if request is not None:
                    trial.update(status='model_candidate_request_review_required', delivery_authorized=False)
            except (ValueError, OSError, KeyError, TypeError, SyntaxError) as exc:
                trial.update(status='model_delivery_blocked', reason=str(exc)[:240])
        trial['comparison'] = comparison
        if receipt is not None:
            trial['receipt_path'] = str(receipt)
            _persist(receipt, trial)
        issue['llm_candidate_trial'] = trial
        issue['causal_feedback'] = {'role': 'architect' if supported else 'analyzer',
            'next_action': 'run_bound_model_delivery_and_full_regression' if issue.get('model_delivery') else
                'review_model_intervention_and_prepare_bound_delivery' if supported
                else 'collect_discriminating_evidence_or_revise_proposals',
            'automatic_retry': False, 'reason': trial['status']}
        if comparison.get('status') == 'no_supported_candidate':
            issue['causal_feedback'].update(role='architect',
                next_action='reconcile_design_and_candidate_with_native_counterexample')
        if trial.get('reason'):
            issue['causal_feedback']['reason'] = trial['reason']
        advisory = trial.get('hypothesis_advisory', {})
        if advisory.get('status') == 'scope_review_required':
            issue['causal_feedback'].update(
                next_action='collect_causal_evidence_before_binding_a_repair_target',
                scope_review=deepcopy(advisory['scope_review']))
        from .candidate_rejection_feedback import REPLAN_REASONS, bind_rejection
        if semantic_retries and trial.get('reason') in REPLAN_REASONS:
            try:
                issue['candidate_validation_feedback']=bind_rejection(project,packet,trial)
            except (ValueError,OSError,KeyError,TypeError) as exc:
                trial['feedback_blocked']=str(exc)
            else:
                issue['prior_llm_trials']=[deepcopy(trial)]
                retried=True
        if semantic_retries and comparison.get('status') == 'no_supported_candidate':
            from .repair_counterexamples import native_counterexamples
            try:
                feedback = native_counterexamples(project, packet, comparison)
            except (ValueError, OSError, KeyError, TypeError) as exc:
                trial['feedback_blocked'] = str(exc)
                if receipt is not None:
                    _persist(receipt, trial)
            else:
                issue['prior_native_comparison'] = deepcopy(comparison)
                issue['native_counterexamples'] = feedback
                issue['prior_llm_trials'] = [deepcopy(trial)]
                retried = True
    if retried:
        result = validate_llm_diagnosis_proposals(result, project=project, root=root, config=config,
            authorized=authorized, delivery_authorized=delivery_authorized, request=request,
            format_retries=0, semantic_retries=0, require_assertion_plan=require_assertion_plan,
            proposal_route=proposal_route, chat=chat, include_dependency_context=include_dependency_context,
            same_class_repairs=same_class_repairs)
        for issue in result.get('issues', []):
            trial = issue.get('llm_candidate_trial')
            if trial and issue.get('prior_llm_trials'):
                trial['native_counterexample_retry'] = issue.get('native_counterexamples') is not None
                trial['candidate_validation_retry'] = issue.get('candidate_validation_feedback') is not None
                trial['total_logical_model_calls'] = trial['logical_model_calls'] + sum(
                    t['logical_model_calls'] for t in issue['prior_llm_trials'])
                if trial.get('receipt_path'):
                    _persist(Path(trial['receipt_path']), trial)
    return result


def _persist(path: Path, trial: dict) -> None:
    path.write_text(json.dumps(trial, ensure_ascii=False, indent=2), encoding='utf-8')
