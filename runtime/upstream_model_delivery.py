"""Integrity contract for delivery of an already tested model intervention."""
import hashlib
from copy import deepcopy

from .native_failure_acceptance import native_coverage
from .project_failure_evidence_packet import is_complete_failure_evidence_packet
from .narrow_type_evidence_binding import content_digest
from .stage_finalization_workspace import inventory, owned_path
from .upstream_llm_candidates import validate_model_candidate, valid_proposal_origin
from .repair_assertion_contract import repair_grounding, validate_assertion_design

AUTHORITY = 'explicit_model_candidate_replay'


def selected_model_candidate(comparison: dict, packet: dict) -> dict:
    attempts = comparison.get('attempts') or []
    supported = [r for r in attempts if r.get('outcome') == 'supported_by_targeted_tests']
    if (not is_complete_failure_evidence_packet(packet, target=str(packet.get('target') or ''))
            or comparison.get('status') != 'selected_for_regression'
            or comparison.get('candidate_origin') != 'llm_structured_proposal'
            or comparison.get('comparison_digest') != content_digest({
                k: v for k, v in comparison.items() if k != 'comparison_digest'})
            or comparison.get('target') != packet.get('target')
            or comparison.get('packet_digest') != packet.get('packet_digest')
            or comparison.get('source_inventory_digest') != packet.get('project_inventory_digest')
            or comparison.get('source_changes') != []
            or not 1 <= len(attempts) <= 4 or len(supported) != 1
            or len({r.get('id') for r in attempts}) != len(attempts)
            or any(r.get('origin') != 'llm_structured_proposal' or r.get('outcome') not in {
                'supported_by_targeted_tests', 'contradicted_by_targeted_tests', 'contradicted_by_preservation_tests'} for r in attempts)):
        raise ValueError('model_delivery_comparison_invalid')
    selected = supported[0]
    evidence = selected.get('evidence') or {}
    proof = selected.get('provenance') or {}
    preservation = proof.get('repair_design', {}).get('preservation_evidence')
    if preservation is not None:
        from .repair_preservation import _passed
        check = selected.get('preservation_check') or {}
        if (check.get('status') != 'passed' or check.get('preservation_digest') != preservation['digest']
                or check.get('same_cases') is not True or not _passed(check.get('probe') or {}, preservation['nodeids'])
                or check['probe']['data']['cases'] != preservation['probes'][0]['data']['cases']):
            raise ValueError('model_delivery_preservation_not_verified')
    if (comparison.get('selected_candidate_id') != selected.get('id')
            or selected.get('operator_id') is not None
            or selected.get('source_sha256') != packet.get('target_source', {}).get('file_sha256')
            or evidence.get('source_inventory_digest') != packet.get('project_inventory_digest')
            or not evidence.get('patched_inventory_digest') or evidence.get('status') != 'passed'
            or not native_coverage(evidence.get('summary') or {}, {packet.get('target')})
            or proof.get('schema_version') != 'upstream_llm_candidate.v1'
            or proof.get('authority') != 'development_trial_only'
            or proof.get('provider_attested') is not False
            or not valid_proposal_origin(proof) or not proof.get('replacement_function')
            or proof.get('provenance_digest') != content_digest({
                k: v for k, v in proof.items() if k != 'provenance_digest'})
            or proof.get('packet_digest') != packet.get('packet_digest')
            or proof.get('target') != packet.get('target')
            or proof.get('replacement_digest') != selected.get('replacement_digest')):
        raise ValueError('model_delivery_selected_evidence_invalid')
    return selected


def validate_delivery_intent(intent: dict) -> dict:
    packet = intent.get('failure_evidence_packet') or {}
    comparison = intent.get('causal_comparison') or {}
    selected = selected_model_candidate(comparison, packet)
    design = selected['provenance'].get('repair_design') or {}
    validate_assertion_design(packet, design)
    if repair_grounding(design):
        expected_grounding = repair_grounding(design)
        if intent.get('repair_grounding') != expected_grounding:
            raise ValueError('model_delivery_grounding_mismatch')
    ticket = intent.get('model_delivery') or {}
    replacement = ticket.get('replacement_source')
    if (intent.get('authority') != AUTHORITY or intent.get('operator_id') is not None
            or intent.get('allowed_operator_ids') != [] or intent.get('target_symbol') != packet.get('target')
            or ticket.get('schema_version') != 'upstream_model_delivery.v1'
            or ticket.get('authority') != AUTHORITY
            or ticket.get('delivery_digest') != content_digest({
                k: v for k, v in ticket.items() if k != 'delivery_digest'})
            or ticket.get('target') != packet.get('target')
            or ticket.get('candidate_id') != selected.get('id')
            or ticket.get('comparison_digest') != comparison.get('comparison_digest')
            or ticket.get('packet_digest') != packet.get('packet_digest')
            or ticket.get('task_contract_digest') != selected['provenance'].get('task_contract_digest')
            or ticket.get('source_inventory_digest') != packet.get('project_inventory_digest')
            or ticket.get('patched_inventory_digest') != selected['evidence']['patched_inventory_digest']
            or ticket.get('source_apply') is not False or ticket.get('promotion_allowed') is not False
            or not isinstance(replacement, str) or len(replacement.encode('utf-8')) > 1_000_000
            or content_digest(replacement) != selected.get('replacement_digest')):
        raise ValueError('model_delivery_intent_invalid')
    return selected


def bind_model_delivery(*, project, issue: dict, candidates: list[dict]) -> dict:
    packet = issue['failure_evidence_packet']
    comparison = issue['causal_comparison']
    selected = selected_model_candidate(comparison, packet)
    candidate = next(r for r in candidates if r['id'] == selected['id'])
    ticket = {'schema_version': 'upstream_model_delivery.v1', 'authority': AUTHORITY,
        'target': packet['target'], 'candidate_id': selected['id'],
        'comparison_digest': comparison['comparison_digest'], 'packet_digest': packet['packet_digest'],
        'task_contract_digest': selected['provenance'].get('task_contract_digest'),
        'source_inventory_digest': packet['project_inventory_digest'],
        'patched_inventory_digest': selected['evidence']['patched_inventory_digest'],
        'replacement_source': candidate['replacement_source'],
        'source_apply': False, 'promotion_allowed': False}
    ticket['delivery_digest'] = content_digest(ticket)
    intent = {'authority': AUTHORITY, 'target_symbol': packet['target'], 'operator_id': None,
        'allowed_operator_ids': [], 'failure_evidence_packet': packet,
        'causal_comparison': comparison, 'model_delivery': ticket}
    design = selected['provenance'].get('repair_design') or {}
    if repair_grounding(design):
        intent['repair_grounding'] = repair_grounding(design)
    validate_delivery_source(project, intent)
    return ticket


def validate_delivery_source(project, intent: dict) -> tuple[dict, str]:
    selected = validate_delivery_intent(intent)
    from .repair_trial_binding import validate_repair_trial_source
    validate_repair_trial_source(project, intent['failure_evidence_packet'])
    preservation = selected.get('provenance', {}).get('repair_design', {}).get('preservation_evidence')
    if preservation is not None:
        from .repair_preservation import validate_preservation
        validate_preservation(intent['failure_evidence_packet'], preservation, project)
    before = inventory(project)
    ticket = intent['model_delivery']
    if content_digest(before) != ticket['source_inventory_digest']:
        raise ValueError('model_delivery_source_changed')
    path = ticket['target'].partition(':')[0]
    original = owned_path(project, path).read_bytes().decode('utf-8')
    replacement = ticket['replacement_source']
    validate_model_candidate({**deepcopy(selected), 'replacement_source': replacement},
                             intent['failure_evidence_packet'], original)
    projected = {**before, path: hashlib.sha256(replacement.encode('utf-8')).hexdigest()}
    if content_digest(projected) != ticket['patched_inventory_digest']:
        raise ValueError('model_delivery_patch_inventory_mismatch')
    return before, original
