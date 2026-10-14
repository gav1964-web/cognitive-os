"""Registered promotion-document preparation, without write authority."""
from __future__ import annotations

from pathlib import Path

from .competency_knowledge import ROOT, invoke_knowledge


def prepare_promotion_catalog(
    *, readiness: dict, evaluator: dict, holdout: dict, generated_at: str,
    competency_root: Path = ROOT,
) -> dict:
    """Return a checked candidate; caller must separately authorize any write."""
    result = invoke_knowledge('exception_pickle', {
        'operation': 'prepare_promotion', 'readiness': readiness, 'evaluator': evaluator,
        'holdout': holdout, 'generated_at': generated_at,
    }, root=competency_root)
    catalog = result.get('catalog')
    if (result.get('status') != 'prepared' or not isinstance(catalog, dict)
            or catalog.get('status') != 'active'):
        raise ValueError('invalid_exception_pickle_promotion_response')
    return catalog
