"""Bind native requested behavior to the exact tested model intervention."""
import uuid
from copy import deepcopy

from .narrow_type_evidence_binding import content_digest
from .stage_finalization_workspace import inventory, owned_path, snapshot
from .upstream_model_delivery import AUTHORITY, validate_delivery_source, validate_delivery_intent
from .upstream_task_contract import normalize_task_contract


def model_request_context(request: dict, project, target: str) -> dict:
    if request.get('status') != 'ready_for_candidate_check':
        raise ValueError('model_request_not_ready:' + str(request.get('reason', 'needs_clarification')))
    contract = normalize_task_contract(request['contract'])
    impact = request.get('impact') or {}
    current = inventory(project)
    if (contract != request['contract'] or impact.get('targets') != [target]
            or impact.get('impact_digest') != content_digest({k: v for k, v in impact.items() if k != 'impact_digest'})
            or any(current.get(p) != h for p, h in impact.get('scanned_sources', {}).items())):
        raise ValueError('model_request_source_or_target_mismatch')
    return deepcopy(contract)


def model_issue_intent(issue: dict) -> dict:
    from .repair_assertion_contract import repair_grounding
    packet = issue.get('failure_evidence_packet') or {}
    intent = {'authority': AUTHORITY, 'target_symbol': packet.get('target'), 'operator_id': None,
        'allowed_operator_ids': [], 'failure_evidence_packet': packet,
        'causal_comparison': issue.get('causal_comparison'), 'model_delivery': issue.get('model_delivery')}
    grounding = repair_grounding(issue.get('repair_design') or {})
    if grounding:
        intent['repair_grounding'] = grounding
    return intent


def requested_model_copy(issue: dict, request: dict, *, project, root):
    intent = model_issue_intent(issue)
    before, _ = validate_delivery_source(project, intent)
    ticket = intent['model_delivery']
    if ticket.get('task_contract_digest') != request['contract']['contract_digest']:
        raise ValueError('model_request_was_not_in_proposal')
    candidate = root.resolve() / 'artifacts/requested_model_candidates' / ('candidate-' + uuid.uuid4().hex[:10])
    if candidate.is_relative_to(project.resolve()) or project.resolve().is_relative_to(candidate):
        raise ValueError('requested_model_copy_must_be_external')
    snapshot(project, candidate, before)
    owned_path(candidate, ticket['target'].partition(':')[0]).write_bytes(ticket['replacement_source'].encode('utf-8'))
    if content_digest(inventory(candidate)) != ticket['patched_inventory_digest']:
        raise ValueError('requested_model_copy_mismatch')
    return candidate


def bind_model_request_ticket(issue: dict, request: dict) -> None:
    ticket = deepcopy(issue['model_delivery'])
    ticket['requested_change_digest'] = request['request_digest']
    ticket['requested_acceptance_digest'] = request['acceptance']['receipt_digest']
    ticket['delivery_digest'] = content_digest({k: v for k, v in ticket.items() if k != 'delivery_digest'})
    issue['model_delivery'] = ticket


def model_request_authority(intent: dict, contract: dict, request: dict, proof: dict) -> bool:
    validate_delivery_intent(intent)
    ticket = intent['model_delivery']
    return bool(ticket.get('task_contract_digest') == contract['contract_digest']
        and ticket.get('requested_change_digest') == request.get('request_digest')
        and ticket.get('requested_acceptance_digest') == proof.get('receipt_digest')
        and ticket.get('patched_inventory_digest') == proof.get('patched_inventory_digest'))
