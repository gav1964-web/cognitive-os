"""Require the final patch to be the same intervention selected before design."""
from .native_failure_acceptance import native_coverage
from .narrow_type_evidence_binding import content_digest
from .review_findings_common import check_row


def causal_comparison_checks(spec: dict, acceptance: dict) -> list[dict]:
    intent = (spec.get('implementation_delta') or {}).get('intent') or {}
    comparison = intent.get('causal_comparison')
    if comparison is None:
        if intent.get('model_delivery') is not None or intent.get('authority') == 'explicit_model_candidate_replay':
            return [check_row('causal_candidate_selection_bound', False, 'Model delivery requires the original comparison.')]
        return []
    packet = intent.get('failure_evidence_packet') or {}
    attempts = comparison.get('attempts', [])
    supported = [r for r in attempts if r.get('outcome') == 'supported_by_targeted_tests']
    selected = supported[0] if len(supported) == 1 else {}
    evidence = selected.get('evidence') or {}
    target = packet.get('target')
    origin_valid = (comparison.get('candidate_origin', 'training_rule_proposal') == 'training_rule_proposal'
                    and selected.get('origin') == 'training_rule_proposal')
    if (comparison.get('candidate_origin') == 'llm_structured_proposal'
            or intent.get('model_delivery') is not None or intent.get('authority') == 'explicit_model_candidate_replay'):
        from .upstream_model_delivery import validate_delivery_intent
        try:
            validate_delivery_intent(intent)
            origin_valid = True
            if intent['model_delivery'].get('task_contract_digest'):
                from .upstream_requested_review import requested_change_checks
                origin_valid = all(r['passed'] for r in requested_change_checks(spec, acceptance))
        except (ValueError, KeyError, TypeError):
            origin_valid = False
    valid = bool(
        comparison.get('status') == 'selected_for_regression'
        and origin_valid
        and comparison.get('comparison_digest') == content_digest({
            k: v for k, v in comparison.items() if k != 'comparison_digest'})
        and comparison.get('target') == target
        and comparison.get('packet_digest') == packet.get('packet_digest')
        and comparison.get('source_inventory_digest') == packet.get('project_inventory_digest')
        and comparison.get('selected_candidate_id') == selected.get('id')
        and selected.get('operator_id') == intent.get('operator_id')
        and all(r.get('outcome') in {'supported_by_targeted_tests', 'contradicted_by_targeted_tests'} for r in attempts)
        and evidence.get('source_inventory_digest') == packet.get('project_inventory_digest')
        and native_coverage(evidence.get('summary') or {}, {target})
        and evidence.get('patched_inventory_digest'))
    same_patch = (not acceptance or (valid and acceptance.get('patched_inventory_digest')
                                    == evidence.get('patched_inventory_digest')))
    return [check_row('causal_candidate_selection_bound', valid,
                     'Design must preserve the unique supported candidate, packet and operator.'),
            check_row('causal_selected_patch_preserved', same_patch,
                      'Executed patch inventory must equal the preselected intervention inventory.')]
