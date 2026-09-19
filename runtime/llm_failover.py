"""Bounded provider failover with process-local cooldowns and safe attempt telemetry."""
from __future__ import annotations

import hashlib
import math
import threading
import time
from dataclasses import replace
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

RETRYABLE_STATUS = {402, 408, 429, 500, 502, 503, 504}
_COOLDOWNS = {}
_LOCK = threading.Lock()


def fallback_configs(profile: dict, config_class) -> tuple:
    from .local_inference import load_llm_profiles, LlmProfileError
    import os
    names = profile.get('fallback_profiles', [])
    if not isinstance(names, list) or len(names) > 2 or len(set(names)) != len(names):
        raise LlmProfileError('fallback_profiles must name at most two distinct profiles')
    profiles = load_llm_profiles()['profiles'] if names else {}
    result = []
    for name in names:
        candidate = profiles.get(name)
        if not isinstance(candidate, dict) or candidate.get('fallback_profiles'):
            raise LlmProfileError('fallback profiles must exist and cannot form chains')
        result.append(config_class(
            base_url=str(candidate['base_url']).rstrip('/'), model=str(candidate['model']),
            api_key=os.environ.get(str(candidate.get('api_key_env', ''))) or None,
            provider_label=str(candidate['provider_label']),
            response_format=bool(candidate.get('response_format', False)),
            timeout_seconds=float(candidate.get('timeout_seconds', 60)),
        ))
    return tuple(result)


def retry_after(value: str | None) -> float:
    if not value:
        return 0
    try:
        seconds = float(value)
    except ValueError:
        try:
            seconds = (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds()
        except (TypeError, ValueError, OverflowError):
            return 0
    return max(0, min(seconds, 86400)) if math.isfinite(seconds) else 0


def call_with_failover(messages, config, call_once):
    from .local_inference import LocalInferenceError
    routes = (config, *config.fallbacks)
    if len(routes) > 3 or len({_key(route) for route in routes}) != len(routes):
        raise LocalInferenceError('invalid or duplicate fallback routes')
    if not config.fallbacks:
        return call_once(messages, config=config)
    last_error = None
    for index, route in enumerate(routes):
        key = _key(route)
        with _LOCK:
            remaining = _COOLDOWNS.get(key, 0) - time.monotonic()
        if remaining > 0:
            _emit(config, {'event': 'route_skipped', 'reason': 'cooldown',
                          'requested_model': route.model, 'provider_label': route.provider_label,
                          'attempt_index': index, 'fallback_used': index > 0})
            continue
        def sink(record, attempt=index):
            _emit(config, {**record, 'attempt_index': attempt, 'fallback_used': attempt > 0})
        selected = replace(route, fallbacks=(), telemetry_sink=sink,
                           advisory_context=config.advisory_context,
                           max_output_tokens=config.max_output_tokens or route.max_output_tokens)
        started = time.monotonic()
        try:
            return call_once(messages, config=selected)
        except LocalInferenceError as exc:
            status = getattr(exc, 'http_status', None)
            retryable = status in RETRYABLE_STATUS or getattr(exc, 'transport_retryable', False)
            _emit(config, {'event': 'attempt_failed', 'requested_model': route.model,
                          'provider_label': route.provider_label, 'http_status': status,
                          'retryable': retryable, 'attempt_index': index, 'fallback_used': index > 0,
                          'latency_seconds': round(time.monotonic() - started, 3)})
            if not retryable:
                raise
            delay = max(3600 if status == 402 else config.failover_cooldown_seconds,
                        getattr(exc, 'retry_after_seconds', 0))
            with _LOCK:
                if len(_COOLDOWNS) >= 256:
                    _COOLDOWNS.pop(min(_COOLDOWNS, key=_COOLDOWNS.get))
                _COOLDOWNS[key] = time.monotonic() + max(1, min(delay, 86400))
            last_error = exc
    if last_error:
        raise last_error
    raise LocalInferenceError('all configured LLM routes are cooling down')


def _key(config):
    credential = hashlib.sha256((config.api_key or '').encode()).hexdigest()
    return config.base_url.rstrip('/'), config.model, credential


def _emit(config, record):
    if config.telemetry_sink:
        try:
            config.telemetry_sink(record)
        except Exception:
            pass
