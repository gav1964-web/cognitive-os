"""Registered JSON serialization proposal client; authorization stays with callers."""
from pathlib import Path

from .competency_knowledge import ROOT, invoke_knowledge
from .helper_proposal import validate_helper_proposal


def propose_json_serialization_patch(
    source: str, *, origin_symbol: str, proposed_symbol: str,
    maximum_free_variables: int, competency_root: Path = ROOT,
) -> dict | None:
    result = invoke_knowledge('json_serialization', {
        'operation': 'propose_patch', 'source': source, 'origin_symbol': origin_symbol,
        'proposed_symbol': proposed_symbol, 'maximum_free_variables': maximum_free_variables,
    }, root=competency_root)
    if result.get('status') == 'not_applicable' and 'patch' in result and result['patch'] is None:
        return None
    if result.get('status') == 'proposed' and isinstance(result.get('patch'), dict) and result['patch']:
        return result['patch']
    raise ValueError('invalid_json_serialization_proposal_response')


def propose_json_serialization_result(
    source: str, *, origin_symbol: str, proposed_symbol: str,
    maximum_free_variables: int, competency_root: Path = ROOT,
) -> dict:
    result = invoke_knowledge('json_serialization', {
        'operation': 'propose_helper', 'source': source, 'origin_symbol': origin_symbol,
        'proposed_symbol': proposed_symbol, 'maximum_free_variables': maximum_free_variables,
    }, root=competency_root)
    if result.get('status') != 'ok':
        raise ValueError('invalid_json_serialization_helper_response')
    return validate_helper_proposal(result.get('proposal'))
