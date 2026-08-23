"""Decide when generated acceptance must reject missing callable input."""

from __future__ import annotations

import inspect
from typing import Any


ACCEPTED_PARAM_KINDS = {
    inspect.Parameter.POSITIONAL_ONLY,
    inspect.Parameter.POSITIONAL_OR_KEYWORD,
    inspect.Parameter.KEYWORD_ONLY,
}


def missing_input_case_required(
    func: object,
    target: str,
    obligations: list[dict[str, Any]],
    *,
    drops_surplus_payload: bool,
) -> bool:
    malformed = [
        row for row in obligations
        if row.get("target") == target and row.get("kind") == "malformed_input_case"
    ]
    if not malformed or drops_surplus_payload:
        return False
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return False
    positive_rows = [
        row for row in obligations
        if row.get("target") == target and row.get("kind") == "positive_contract_case"
    ]
    positive_keys = {str(key) for row in positive_rows for key in dict(row.get("given", {}))}
    explicit = {name for name, param in signature.parameters.items() if param.kind in ACCEPTED_PARAM_KINDS}
    required = {
        name for name, param in signature.parameters.items()
        if param.kind in ACCEPTED_PARAM_KINDS and param.default is inspect.Parameter.empty
    }
    accepts_keywords = any(
        param.kind == inspect.Parameter.VAR_KEYWORD
        for param in signature.parameters.values()
    )
    if accepts_keywords and any(positive_keys - set(dict(row.get("given", {}))) for row in malformed):
        return True
    if not required:
        return False
    for row in malformed:
        given = dict(row.get("given", {}))
        try:
            signature.bind(**given)
        except TypeError:
            return True
        if positive_keys - set(given) - explicit:
            return True
    return False
