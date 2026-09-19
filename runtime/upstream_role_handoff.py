"""Keep requested behavior through the first three roles without granting execution."""
from copy import deepcopy
from pathlib import Path

from .narrow_type_evidence_binding import content_digest
from .upstream_task_contract import analyze_task_contract, normalize_task_contract, task_analysis_current


def frame_analysis(report: dict, task_contract: dict | None, product_context: dict | None = None) -> dict:
    result = deepcopy(report)
    result['reasoning_provenance'] = {
        'builder': 'runtime.role_project_analysis', 'source_facts': 'inspect_and_static_analysis',
        'interpretation': 'configured_rules_and_templates', 'goal_understanding': 'not_independently_verified',
        'causal_diagnosis': 'not_established_by_project_map', 'confidence_calibration': 'not_measured'}
    if task_contract is not None:
        contract = normalize_task_contract(task_contract)
        result['task_contract'] = contract
        result['task_analysis'] = analyze_task_contract(Path(result.get('root') or result['summary']['root']), contract)
    if product_context is not None:
        from .product_context import forward_product_context
        forward_product_context(result, {'product_context': product_context}, result.get('root') or result['summary']['root'])
    return result


def frame_architecture(artifact: dict, analysis: dict) -> dict:
    artifact['reasoning_provenance'] = {
        'builder': 'runtime.architecture_decision_builder',
        'options': 'configured_policy_proposals', 'source_context': 'static_source_observations',
        'confidence_calibration': 'not_measured', 'semantic_design_validation': 'not_measured',
        'llm_advisory': deepcopy(artifact.get('architect_advisory') or {})}
    from .product_context import forward_product_context
    forward_product_context(artifact, analysis, artifact['project'])
    if 'product_context' in artifact:
        artifact['spec_writer_brief']['product_context'] = deepcopy(artifact['product_context'])
    if 'task_contract' not in analysis:
        return artifact
    contract = normalize_task_contract(analysis['task_contract'])
    project = Path(artifact['project'])
    task_analysis = deepcopy(analysis.get('task_analysis') or {})
    current = task_analysis_current(project, contract, task_analysis)
    if not current:
        task_analysis = analyze_task_contract(project, contract)
    ready = current and task_analysis['status'] == 'source_bound'
    targets = list(dict.fromkeys(t for r in contract['requirements'] for t in r.get('targets', [])))
    kind = contract['change_kind']
    options = [
        {'id': 'bounded_in_place_change', 'title': 'Change the requested behavior within the existing API boundary.',
         'tradeoffs': ['preserves callers', 'does not separate responsibilities'], 'applicable': kind in {'defect', 'feature'}},
        {'id': 'separate_behind_existing_api', 'title': 'Separate responsibilities behind the existing public entrypoint.',
         'tradeoffs': ['allows isolated testing', 'requires caller and compatibility analysis'], 'applicable': kind == 'architecture'},
        {'id': 'clarify_before_change', 'title': 'Resolve missing or conflicting requirements before selecting a change.',
         'tradeoffs': ['avoids inventing intended behavior', 'implementation remains deferred'], 'applicable': not ready},
    ]
    chosen = next(row for row in options if row['applicable']) if ready else options[-1]
    artifact.update(task_contract=contract, task_analysis=task_analysis,
        architecture_options=options, chosen_option=deepcopy(chosen),
        rejected_options=[{'id': row['id'], 'reason': 'outside supplied change kind or clarification state'}
                          for row in options if row['id'] != chosen['id']],
        task_design_status='proposal_requires_validation' if ready else 'needs_clarification',
        decision_summary=chosen['title'],
        first_slice_contract={'name': 'requested_behavior_change', 'targets': targets if ready else [],
                              'goal': artifact['goal'], 'steps': [r['statement'] for r in contract['requirements']]},
        open_questions=[{'question': 'Validate behavioral cause, affected callers and implementation mechanism.',
                         'origin': 'unresolved_design_work'},
                        *[{'question': f'Resolve conflicting constraint: {key}'} for key in task_analysis['conflicting_constraints']]])
    if not current:
        artifact['open_questions'].append({'question': 'Analyzer source bindings were absent or stale; repeat analysis.'})
    artifact['spec_writer_brief'].update(
        scope=[r['statement'] for r in contract['requirements']], files_or_symbols=targets if ready else [],
        first_slice=artifact['first_slice_contract'], requested_requirements=deepcopy(contract['requirements']),
        task_contract_digest=contract['contract_digest'])
    artifact['reasoning_provenance']['requirements'] = contract['origin']
    artifact['reasoning_provenance']['options'] = 'change_kind_policy_proposals; not independent architecture reasoning'
    if analysis.get('diagnostic_hypotheses'):
        artifact['supplied_hypotheses'] = deepcopy(analysis['diagnostic_hypotheses'])
        artifact['reasoning_provenance']['hypotheses'] = 'assistant_supplied_diagnostic_input; not verified'
    return artifact


def frame_specification(artifact: dict, architecture: dict) -> dict:
    artifact['reasoning_provenance'] = {'builder': 'runtime.technical_spec_builder',
        'requirements': 'architecture_brief_and_configured_rules',
        'acceptance': 'configured_templates_and_source_inference', 'semantic_completeness': 'not_measured'}
    from .product_context import forward_product_context
    forward_product_context(artifact, architecture, architecture['project'])
    if 'task_contract' not in architecture:
        return artifact
    contract = normalize_task_contract(architecture['task_contract'])
    requirements, criteria, traceability = [], [], []
    gaps = []
    for row in contract['requirements']:
        requirements.append({**deepcopy(row), 'priority': 'MUST', 'source': 'task_contract', 'origin': contract['origin']})
        ids = []
        for index, example in enumerate(row.get('acceptance_examples', [])):
            ident = f"AC-REQUEST-{row['id']}-{index + 1}"
            criteria.append({'id': ident, 'requirement_id': row['id'], 'criterion': row['statement'],
                'source': row.get('targets', [None])[0] if row.get('targets') else None,
                'example': deepcopy(example), 'verification': 'review' if example.get('kind') == 'review' else 'behavioral_test_required',
                'execution_status': 'not_run', 'origin': contract['origin']})
            ids.append(ident)
        if not ids:
            gaps.append({'requirement_id': row['id'], 'reason': 'acceptance_observation_missing'})
        traceability.append({'requirement_id': row['id'], 'acceptance_ids': ids, 'targets': row.get('targets', [])})
    # A supplied example is not an implementation design or evidence of a passing test.
    gaps.append({'reason': 'implementation_mechanism_and_effects_require_validation'})
    state = architecture.get('task_design_status')
    artifact.update(task_contract=deepcopy(contract), requirements=requirements,
        requested_acceptance_criteria=criteria, requirement_traceability=traceability,
        task_handoff={'status': 'needs_clarification' if state == 'needs_clarification' else 'needs_design',
                      'gaps': gaps, 'contract_digest': contract['contract_digest'], 'execution_authorized': False},
        implementation_delta={'status': 'blocked', 'reason': 'requested_change_design_not_verified',
                              'task_contract_digest': contract['contract_digest']})
    artifact['acceptance_criteria'] = [*criteria, *artifact.get('acceptance_criteria', [])]
    artifact['implementation_handoff']['mode'] = 'blocked'
    artifact['requested_constraints'] = deepcopy(contract['constraints'])
    if architecture.get('design_proposal'):
        artifact['implementation_design_proposal'] = deepcopy(architecture['design_proposal'])
        artifact['reasoning_provenance']['design'] = 'assistant_supplied_diagnostic_input; validation required'
    artifact['reasoning_provenance'].update(requirements=contract['origin'],
        acceptance='caller_supplied_examples_preserved; not independently generated or executed')
    artifact['task_handoff']['handoff_digest'] = content_digest(artifact['task_handoff'])
    return artifact
