"""Pluggable local inference client for Level 3.5."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
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
    response_format: bool = True
    api_key: str | None = None
    provider_label: str = "local"
    telemetry_sink: Callable[[dict[str, Any]], None] | None = None

    @classmethod
    def from_env(cls) -> "LocalInferenceConfig":
        profile = _profile("local_l35", _LOCAL_L35_DEFAULTS)
        api_key_env = os.environ.get("COGNITIVE_OS_LLM_API_KEY_ENV", str(profile.get("api_key_env") or "COGNITIVE_OS_LLM_API_KEY"))
        return cls(
            base_url=os.environ.get("COGNITIVE_OS_LLM_BASE_URL", str(profile["base_url"])).rstrip("/"),
            model=os.environ.get("COGNITIVE_OS_LLM_MODEL", str(profile["model"])),
            timeout_seconds=float(os.environ.get("COGNITIVE_OS_LLM_TIMEOUT", str(profile["timeout_seconds"]))),
            response_format=_env_bool("COGNITIVE_OS_LLM_RESPONSE_FORMAT", bool(profile["response_format"])),
            api_key=os.environ.get(api_key_env) or os.environ.get("COGNITIVE_OS_LLM_API_KEY") or None,
            provider_label=os.environ.get("COGNITIVE_OS_LLM_PROVIDER", str(profile["provider_label"])),
        )

    @classmethod
    def from_l45_env(cls) -> "LocalInferenceConfig":
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
        )


def call_json_chat(messages: list[dict[str, str]], *, config: LocalInferenceConfig | None = None) -> dict[str, Any]:
    cfg = config or LocalInferenceConfig.from_env()
    started = time.perf_counter()
    payload = {
        "model": cfg.model,
        "temperature": 0,
        "messages": messages,
    }
    if cfg.response_format:
        payload["response_format"] = {"type": "json_object"}
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
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise LocalInferenceError(f"local inference request failed: HTTP {exc.code}: {body}") from exc
    except Exception as exc:
        raise LocalInferenceError(f"local inference request failed: {exc}") from exc
    _emit_telemetry(cfg, response_payload, time.perf_counter() - started)
    try:
        content = response_payload["choices"][0]["message"]["content"]
        result = _loads_json_object(str(content))
    except Exception as exc:
        raise LocalInferenceError("local inference response is not a JSON object") from exc
    if not isinstance(result, dict):
        raise LocalInferenceError("local inference response must decode to object")
    return result


def _emit_telemetry(config: LocalInferenceConfig, response_payload: dict[str, Any], elapsed_seconds: float) -> None:
    if config.telemetry_sink is None:
        return
    usage = response_payload.get("usage")
    usage = usage if isinstance(usage, dict) else {}
    record = {
        "model": str(response_payload.get("model") or config.model),
        "provider_label": config.provider_label,
        "latency_seconds": round(elapsed_seconds, 3),
        "prompt_tokens": _optional_int(usage.get("prompt_tokens")),
        "completion_tokens": _optional_int(usage.get("completion_tokens")),
        "total_tokens": _optional_int(usage.get("total_tokens")),
        "usage_reported": bool(usage),
    }
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
