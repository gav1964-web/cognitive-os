"""Separate installed KB reads from validation of explicit research documents."""
from __future__ import annotations

import json
from pathlib import Path

from .competency_knowledge import ROOT, invoke_knowledge

# Compatibility layout of existing research roots; not a second knowledge owner.
RESEARCH_CATALOG_PATH = Path('plugins/exception_pickle/knowledge/exception_pickle_reconstruction_patterns.json')


def read_installed_patterns(*, competency_root: Path = ROOT) -> dict:
    """Read the registered installation's current KB, with code+KB admission."""
    result = invoke_knowledge('exception_pickle', {'operation': 'patterns'}, root=competency_root)
    return _catalog(result)


def validate_research_patterns(document: dict | None, *, competency_root: Path = ROOT) -> dict:
    """Check supplied data; active inside this document is not registry admission.

None represents a missing research document, with the prior absent semantics.
The installed validator's identity is checked, not the document's provenance or
independent evaluation. Consumers retain their existing outer evidence gates.
"""
    result = invoke_knowledge('exception_pickle', {
        'operation': 'validate_patterns', 'document': document,
    }, root=competency_root)
    return _catalog(result)


def read_research_patterns(path: Path, *, competency_root: Path = ROOT) -> dict:
    """Read only the explicit path, fresh each call; never fall back to live KB."""
    document = json.loads(path.read_text(encoding='utf-8')) if path.exists() else None
    return validate_research_patterns(document, competency_root=competency_root)


def _catalog(result: dict) -> dict:
    if result.get('status') != 'ok' or not isinstance(result.get('catalog'), dict):
        raise ValueError('invalid_exception_pickle_catalog_response')
    return result['catalog']
