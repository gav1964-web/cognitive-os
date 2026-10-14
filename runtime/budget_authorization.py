"""Explicit operator-provided budget grants; never inferred from exhausted usage."""
import json
from pathlib import Path


def validate_grant(grant, limit):
    if (not isinstance(grant, dict) or grant.get('schema_version') != 'budget_authorization.v1'
            or grant.get('authority') != 'user' or not str(grant.get('reason', '')).strip()
            or type(limit) is not int or not 1_000_000 < limit <= 10_000_000
            or grant.get('limit_exclusive') != limit):
        raise ValueError('explicit_budget_authorization_required')
    return grant


def load_grant(path, limit):
    if path is None:
        raise ValueError('explicit_budget_authorization_required')
    return validate_grant(json.loads(Path(path).read_text(encoding='utf-8')), limit)
