"""Neutral proposal boundary; metadata cannot replace coordinator-owned fields."""
from copy import deepcopy


RESERVED_OPERATION_FIELDS = {
    'artifact_type', 'kind', 'target', 'file', 'created_target', 'diff',
}


def validate_helper_proposal(value: dict) -> dict:
    required = {'schema_version', 'status', 'source', 'operation_details', 'reason'}
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError('invalid_helper_proposal_fields')
    if value['schema_version'] != 'helper_proposal.v1':
        raise ValueError('invalid_helper_proposal_version')
    details = value['operation_details']
    if not isinstance(details, dict) or any(not isinstance(k, str) for k in details):
        raise ValueError('invalid_helper_proposal_details')
    if RESERVED_OPERATION_FIELDS.intersection(details):
        raise ValueError('helper_proposal_overrides_coordinator_fields')
    if value['status'] == 'proposed':
        if not isinstance(value['source'], str) or value['reason'] is not None:
            raise ValueError('invalid_proposed_helper')
    elif value['status'] == 'not_applicable':
        if value['source'] is not None or details or not isinstance(value['reason'], str) or not value['reason']:
            raise ValueError('invalid_helper_refusal')
    else:
        raise ValueError('invalid_helper_proposal_status')
    return deepcopy(value)


def legacy_helper_proposal(patch: dict | None, *, fields: tuple[str, ...], reason: str) -> dict:
    """Adapt remaining local extractors without copying their algorithms."""
    return validate_helper_proposal({
        'schema_version': 'helper_proposal.v1',
        'status': 'proposed' if patch is not None else 'not_applicable',
        'source': patch['source'] if patch is not None else None,
        'operation_details': {key: patch[key] for key in fields} if patch is not None else {},
        'reason': None if patch is not None else reason,
    })
