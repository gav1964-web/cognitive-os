"""Bounded, domain-neutral provider failure metadata; never retain raw error bodies."""
import json
import re

UNUSABLE_OUTCOMES = {'refusal', 'suspected_stub', 'service_error', 'empty',
                     'provider_response_unusable', 'invalid_response_format'}


def completion_failure(payload):
    """Interpret declared provider outcomes, never classify domain response text."""
    details = payload.get('provider_diagnostics')
    if not isinstance(details, dict):
        return {}
    status = details.get('response_status')
    if not isinstance(status, str) or status not in UNUSABLE_OUTCOMES:
        return {}
    return safe_metadata({'error': {'code': status}, 'provider_diagnostics': details})


def safe_metadata(payload):
    if not isinstance(payload, dict):
        return {}
    error = payload.get('error')
    if not isinstance(error, dict):
        return {}
    result = {}
    for key in ('code', 'provider', 'run_id', 'request_id'):
        value = error.get(key)
        if isinstance(value, str) and re.fullmatch(r'[a-zA-Z0-9_.:-]{1,128}', value):
            result[key] = value
    details = payload.get('provider_diagnostics', {})
    if isinstance(details, dict):
        checked = {}
        for key in ('run_id', 'transport_status', 'response_status', 'browser_model'):
            value = details.get(key)
            if isinstance(value, str) and re.fullmatch(r'[a-zA-Z0-9_.: -]{1,128}', value):
                checked[key] = value
        for key in ('requested_model', 'resolved_model'):
            value = details.get(key)
            if isinstance(value, str) and re.fullmatch(r'[a-zA-Z0-9_./:-]{1,128}', value):
                checked[key] = value
        if type(details.get('retry_count')) is int and 0 <= details['retry_count'] <= 10:
            checked['retry_count'] = details['retry_count']
        if checked:
            result['diagnostics'] = checked
    return result


def attach_http_evidence(failure, response, config, elapsed):
    usage = None
    try:
        raw = response.read(16385)
        payload = json.loads(raw) if len(raw) <= 16384 else {}
        failure.provider_failure = safe_metadata(payload)
        usage = checked_usage(payload.get('usage')) if isinstance(payload, dict) else None
    except (OSError, ValueError, TypeError, AttributeError):
        failure.provider_failure = {}
    failure.provider_usage = usage
    evidence = failure_evidence(failure)
    if config.telemetry_sink and evidence:
        try:
            config.telemetry_sink({'event': 'provider_unavailable', 'requested_model': config.model,
                'latency_seconds': round(elapsed, 3),
                'usage_reported': usage is not None and type(usage.get('total_tokens')) is int,
                **(usage or {}), **evidence})
        except Exception:
            pass


def failure_evidence(error):
    status = getattr(error, 'http_status', None)
    metadata = getattr(error, 'provider_failure', {})
    code = metadata.get('code') if isinstance(metadata, dict) else None
    declared_unusable = isinstance(code, str) and code in UNUSABLE_OUTCOMES
    if (status not in {402, 408, 409, 429, 500, 502, 503, 504}
            and not getattr(error, 'transport_retryable', False) and not declared_unusable):
        return {}
    result = {'http_status': status, 'provider_failure': metadata,
              'quality_evaluation': 'not_evaluated'}
    usage = checked_usage(getattr(error, 'provider_usage', None))
    if usage is not None:
        result['usage'] = usage
    return result


def checked_usage(value):
    """Use reported counts; derive a missing total only from both valid components."""
    if not isinstance(value, dict):
        return None
    result = {key: value[key] for key in ('prompt_tokens', 'completion_tokens', 'total_tokens')
              if type(value.get(key)) is int and 0 <= value[key] <= 2**63 - 1}
    if ('total_tokens' not in value and 'prompt_tokens' in result
            and 'completion_tokens' in result):
        total = result['prompt_tokens'] + result['completion_tokens']
        if total <= 2**63 - 1:
            result['total_tokens'] = total
    return result or None
