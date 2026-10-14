"""Registered text splitting proposal client; authorization stays with callers."""
from pathlib import Path

from .competency_knowledge import ROOT, invoke_knowledge
from .helper_proposal import validate_helper_proposal


def propose_text_splitting_patch(
    source: str, *, origin_symbol: str, proposed_symbol: str,
    competency_root: Path = ROOT,
) -> dict | None:
    result = invoke_knowledge('text_splitting', {
        'operation': 'propose_patch', 'source': source, 'origin_symbol': origin_symbol,
        'proposed_symbol': proposed_symbol,
    }, root=competency_root)
    if result.get('status') == 'not_applicable' and 'patch' in result and result['patch'] is None:
        return None
    if result.get('status') == 'proposed' and isinstance(result.get('patch'), dict) and result['patch']:
        return result['patch']
    raise ValueError('invalid_text_splitting_proposal_response')


def propose_text_splitting_result(
    source: str, *, origin_symbol: str, proposed_symbol: str,
    competency_root: Path = ROOT,
) -> dict:
    result = invoke_knowledge('text_splitting', {
        'operation': 'propose_helper', 'source': source, 'origin_symbol': origin_symbol,
        'proposed_symbol': proposed_symbol,
    }, root=competency_root)
    if result.get('status') != 'ok':
        raise ValueError('invalid_text_splitting_helper_response')
    return validate_helper_proposal(result.get('proposal'))
