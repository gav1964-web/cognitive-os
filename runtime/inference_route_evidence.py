"""Allowlisted gateway claims; never credentials or billing attestation."""
import math
import re


def route_evidence(headers):
    if headers is None:
        return {}
    result = {}
    raw = headers.get('X-Cache-Hit')
    if raw in {'0', '1'}:
        result['cache_hit'] = raw == '1'
    for header, key in (
        ('X-Route-Requested-Model', 'requested_model'),
        ('X-Route-Resolved-Profile', 'resolved_profile'),
        ('X-Route-Attempted-Models', 'attempted_models'),
        ('X-Route-Complexity', 'complexity'),
        ('X-Route-Decision', 'decision'),
    ):
        value = headers.get(header)
        if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_.:/, -]{1,160}', value):
            if key == 'attempted_models':
                models = value.split(',')
                if len(models) <= 8 and all(m.strip() for m in models):
                    result[key] = [m.strip() for m in models]
            else:
                result[key] = value
    try:
        duration = float(headers.get('X-Request-Duration-Seconds'))
        if math.isfinite(duration) and 0 <= duration <= 86400:
            result['duration_seconds'] = duration
    except (ValueError, TypeError):
        pass
    if result:
        result['authority'] = 'gateway_reported_not_provider_attested'
    return result
