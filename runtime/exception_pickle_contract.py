"""Typed client for the registered exception-pickle proposal contract.

The competency installation is independent of a research corpus/project root.
Admission errors propagate; they are never retried through a private owner API.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .competency_knowledge import ROOT, invoke_knowledge


def propose_exception_pickle_patch(
    source: str, *, class_name: str, recipe: dict[str, Any],
    constructor_name: str = '__init__', competency_root: Path = ROOT,
) -> dict[str, Any] | None:
    """Return an admitted proposal, or None only for explicit not_applicable.

This does not apply a patch or admit an experimental recipe as active knowledge.
Consumers retain their authorization, sandbox, native replay and review gates.
"""
    result = invoke_knowledge('exception_pickle', {
        'operation': 'propose_patch', 'source': source, 'class_name': class_name,
        'recipe': recipe, 'constructor_name': constructor_name,
    }, root=competency_root)
    if result.get('status') == 'not_applicable' and 'patch' in result and result['patch'] is None:
        return None
    if result.get('status') == 'proposed' and isinstance(result.get('patch'), dict) and result['patch']:
        return result['patch']
    raise ValueError('invalid_exception_pickle_proposal_response')
