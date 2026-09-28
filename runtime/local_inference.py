"""Pluggable local inference client for Level 3.5."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable
from urllib import error, request

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE_PATH = ROOT / "config" / "llm_profiles.json"


class LocalInferenceError(RuntimeError):
    """Raised when the local inference backend is unavailable or invalid."""


class LlmProfileError(RuntimeError):
    """Raised when LLM profile configuration is invalid."""


_LOCAL_L35_DEFAULTS = {
    "api_key_env": "COGNITIVE_OS_LLM_API_KEY",
    "base_url": "http://127.0.0.1:8000/v1",
    "model": "local",
    "provider_label": "local",
    "response_format": True,
    "timeout_seconds": 20,
}
_L45_DEFAULTS = {
    "api_key_env": "COGNITIVE_OS_L45_API_KEY",
    "base_url": "http://127.0.0.1:8000/v1",
    "model": "deepseek/deepseek-chat",
    "provider_label": "external_l45_intent_resolver",
    "response_format": False,
    "timeout_seconds": 60,
}


@lru_cache(maxsize=1)
def load_llm_profiles(path: str | None = None) -> dict[str, Any]:
    source = Path(path) if path else DEFAULT_PROFILE_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "llm_profiles.v1":
        raise LlmProfileError("LLM profiles must use schema_version llm_profiles.v1")
    profiles = payload.get("profiles")
    if not isinstance(profiles, dict):
        raise LlmProfileError("LLM profiles config must contain profiles object")
    for profile_id, profile in profiles.items():
        if not isinstance(profile, dict):
            raise LlmProfileError(f"LLM profile {profile_id} must be an object")
        for field in ("base_url", "model", "provider_label"):
            if not str(profile.get(field) or "").strip():
                raise LlmProfileError(f"LLM profile {profile_id} requires {field}")
    for profile_id, profile in profiles.items():
        from .llm_failover import fallback_codes
        fallback_codes(profile)
        fallbacks = profile.get('fallback_profiles', [])
        if (not isinstance(fallbacks, list) or len(fallbacks) > 2
                or not all(isinstance(name, str) for name in fallbacks)
                or len(set(fallbacks)) != len(fallbacks)):
            raise LlmProfileError('invalid fallback profile list')
        if any(name == profile_id or name not in profiles or profiles[name].get('fallback_profiles') for name in fallbacks):
            raise LlmProfileError('fallback profiles must exist and cannot form chains')
    return payload


def _profile(profile_id: str, fallback: dict[str, Any]) -> dict[str, Any]:
    try:
        profile = dict(dict(load_llm_profiles().get("profiles") or {}).get(profile_id) or {})
    except (OSError, json.JSONDecodeError, LlmProfileError):
        profile = {}
    return {**fallback, **profile}


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class LocalInferenceConfig:
    base_url: str
    model: str
    timeout_seconds: float = 20.0
    response_format: bool | dict[str, Any] = True
    api_key: str | None = field(default=None, repr=False)
    provider_label: str = "local"
    telemetry_sink: Callable[[dict[str, Any]], None] | None = None
    advisory_context: dict[str, Any] | None = None
    max_output_tokens: int | None = None
    fallbacks: tuple["LocalInferenceConfig", ...] = ()
    failover_cooldown_seconds: float = 60.0
    fallback_on_codes: tuple[str, ...] = ()
    strict_json: bool = False
    response_schema: dict[str, Any] | None = None
    raw_response_sink: Callable[[dict[str, Any]], None] | None = field(default=None, repr=False)
    raw_response_limit_bytes: int = 262144

    @classmethod
    def from_env(cls) -> "LocalInferenceConfig":
        from .llm_failover import fallback_configs, fallback_codes
        profile = _profile("local_l35", _LOCAL_L35_DEFAULTS)
        api_key_env = os.environ.get("COGNITIVE_OS_LLM_API_KEY_ENV", str(profile.get("api_key_env") or "COGNITIVE_OS_LLM_API_KEY"))
        return cls(
            base_url=os.environ.get("COGNITIVE_OS_LLM_BASE_URL", str(profile["base_url"])).rstrip("/"),
            model=os.environ.get("COGNITIVE_OS_LLM_MODEL", str(profile["model"])),
            timeout_seconds=float(os.environ.get("COGNITIVE_OS_LLM_TIMEOUT", str(profile["timeout_seconds"]))),
            response_format=_env_bool("COGNITIVE_OS_LLM_RESPONSE_FORMAT", bool(profile["response_format"])),
            api_key=os.environ.get(api_key_env) or os.environ.get("COGNITIVE_OS_LLM_API_KEY") or None,
            provider_label=os.environ.get("COGNITIVE_OS_LLM_PROVIDER", str(profile["provider_label"])),
            fallbacks=fallback_configs(profile, cls),
            fallback_on_codes=fallback_codes(profile),
        )

    @classmethod
    def from_l45_env(cls) -> "LocalInferenceConfig":
        from .llm_failover import fallback_configs, fallback_codes
        profile = _profile("external_l45_intent_resolver", _L45_DEFAULTS)
        api_key_env = os.environ.get(
            "COGNITIVE_OS_L45_API_KEY_ENV",
            str(profile.get("api_key_env") or "COGNITIVE_OS_L45_API_KEY"),
        )
        return cls(
            base_url=os.environ.get("COGNITIVE_OS_L45_BASE_URL", str(profile["base_url"])).rstrip("/"),
            model=os.environ.get("COGNITIVE_OS_L45_MODEL", str(profile["model"])),
            timeout_seconds=float(os.environ.get("COGNITIVE_OS_L45_TIMEOUT", str(profile["timeout_seconds"]))),
            response_format=_env_bool("COGNITIVE_OS_L45_RESPONSE_FORMAT", bool(profile["response_format"])),
            api_key=os.environ.get(api_key_env)
            or os.environ.get(str(profile.get("api_key_env") or "COGNITIVE_OS_L45_API_KEY"))
            or None,
            provider_label=str(profile["provider_label"]),
            fallbacks=fallback_configs(profile, cls),
            fallback_on_codes=fallback_codes(profile),
        )


def call_json_chat(messages: list[dict[str, str]], *, config: LocalInferenceConfig | None = None) -> dict[str, Any]:
    from .llm_failover import call_with_failover
    return call_with_failover(messages, config or LocalInferenceConfig.from_env(), _call_json_chat_once)


def _call_json_chat_once(messages: list[dict[str, str]], *, config: LocalInferenceConfig) -> dict[str, Any]:
    cfg = config or LocalInferenceConfig.from_env()
    from .structured_inference import check_config, capture_response, parse_document
    check_config(cfg)
    # Pre-network validation of max_output_tokens per contract
    m = cfg.max_output_tokens
    if m is not None:
        if type(m) is not int or m <= 0:
            raise LocalInferenceError("max_output_tokens must be a positive integer or None")
    started = time.perf_counter()
    payload = {
        "model": cfg.model,
        "temperature": 0,
        "messages": messages,
    }
    if isinstance(cfg.response_format, dict):
        from copy import deepcopy
        payload["response_format"] = deepcopy(cfg.response_format)
    elif cfg.response_format:
        payload["response_format"] = {"type": "json_object"}
    if cfg.max_output_tokens is not None:
        payload["max_tokens"] = cfg.max_output_tokens
    headers = {"Content-Type": "application/json"}
    if cfg.api_key:
        headers["Authorization"] = f"Bearer {cfg.api_key}"
    http_request = request.Request(
        f"{cfg.base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with request.urlopen(http_request, timeout=cfg.timeout_seconds) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
            from .inference_route_evidence import route_evidence
            route = route_evidence(getattr(response, 'headers', None))
    except error.HTTPError as exc:
        from .llm_failover import retry_after
        failure = LocalInferenceError(f"local inference request failed: HTTP {exc.code}")
        failure.http_status = exc.code
        failure.retry_after_seconds = retry_after(exc.headers.get('Retry-After') if exc.headers else None)
        from .inference_failure_evidence import attach_http_evidence
        attach_http_evidence(failure, exc, cfg, time.perf_counter() - started)
        exc.close()
        raise failure from exc
    except Exception as exc:
        import ssl
        failure = LocalInferenceError(f"local inference request failed: {type(exc).__name__}")
        failure.transport_retryable = isinstance(exc, (error.URLError, TimeoutError, ConnectionError)) and not isinstance(
            getattr(exc, 'reason', exc), ssl.SSLCertVerificationError)
        raise failure from exc
    if not isinstance(response_payload, dict):
        raise LocalInferenceError("local inference response must be an object")
    _emit_telemetry(cfg, response_payload, time.perf_counter() - started, route=route)
    raw_record = capture_response(cfg, response_payload)
    from .inference_failure_evidence import completion_failure
    if evidence := completion_failure(response_payload):
        failure = LocalInferenceError('provider returned ' + evidence['code'])
        failure.http_status = 200
        failure.provider_failure = evidence
        raise failure
    try:
        if any(choice.get("finish_reason") == "length" for choice in response_payload.get("choices", [])):
            raise LocalInferenceError("local inference response was truncated")
        content = response_payload["choices"][0]["message"]["content"]
        if content is None or (isinstance(content, str) and not content.strip()):
            raise LocalInferenceError("local inference response has empty final content")
        if raw_record and raw_record['truncated']:
            raise LocalInferenceError('raw response exceeds evidence limit')
        strict = cfg.strict_json or cfg.response_schema is not None or isinstance(cfg.response_format, dict)
        result = parse_document(content, cfg.response_schema) if strict else _loads_json_object(str(content))
    except LocalInferenceError as exc:
        if raw_record is not None:
            exc.response_evidence = raw_record
        raise
    except Exception as exc:
        raise LocalInferenceError("local inference response is not a JSON object") from exc
    if not isinstance(result, dict):
        raise LocalInferenceError("local inference response must decode to object")
    return result


def _emit_telemetry(config: LocalInferenceConfig, response_payload: dict[str, Any], elapsed_seconds: float,
                    *, route: dict | None = None) -> None:
    if config.telemetry_sink is None:
        return
    usage = response_payload.get("usage")
    usage = usage if isinstance(usage, dict) else {}
    record = {
        "model": str(response_payload.get("model") or config.model),
        "requested_model": config.model,
        "model_reported": bool(response_payload.get("model")),
        "provider_label": config.provider_label,
        "latency_seconds": round(elapsed_seconds, 3),
        "prompt_tokens": _optional_int(usage.get("prompt_tokens")),
        "completion_tokens": _optional_int(usage.get("completion_tokens")),
        "total_tokens": _optional_int(usage.get("total_tokens")),
        "usage_reported": bool(usage),
    }
    choices = response_payload.get('choices')
    choice = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], dict) else {}
    message = choice.get('message')
    content = message.get('content') if isinstance(message, dict) else None
    finish = choice.get('finish_reason')
    record['finish_reason'] = finish if isinstance(finish, str) and finish in {
        'stop', 'length', 'tool_calls', 'content_filter', 'function_call'} else None
    record['final_content_state'] = ('missing' if content is None else
        'empty' if isinstance(content, str) and not content.strip() else
        'present' if isinstance(content, str) else 'invalid_type')
    record['final_content_characters'] = len(content) if isinstance(content, str) else None
    from .inference_web_evidence import checked_web_evidence
    diagnostics = response_payload.get('provider_diagnostics')
    if isinstance(diagnostics, dict) and isinstance(content, str):
        from .inference_failure_evidence import safe_metadata
        provider = safe_metadata({'error': {}, 'provider_diagnostics': diagnostics}).get('diagnostics')
        if provider:
            record['provider_diagnostics'] = provider
        web_evidence = checked_web_evidence(diagnostics.get('web_evidence'), content)
        if web_evidence is not None:
            record['web_evidence'] = web_evidence
    if route:
        record['gateway_route'] = route
        record['billing_evidence'] = 'unknown; token usage and gateway cache claims are not invoices'
    from .inference_failure_evidence import completion_failure
    if evidence := completion_failure(response_payload):
        record.update(provider_failure=evidence, quality_evaluation='not_evaluated')
    try:
        config.telemetry_sink(record)
    except Exception:
        return


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _loads_json_object(content: str) -> dict[str, Any]:
    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        result = _first_embedded_json_object(content)
    if not isinstance(result, dict):
        raise LocalInferenceError("local inference response must decode to object")
    return result


def _first_embedded_json_object(content: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    for index, character in enumerate(content):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(content[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise json.JSONDecodeError("no JSON object found", content, 0)
