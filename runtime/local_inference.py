"""Pluggable local inference client for Level 3.5."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Callable
from urllib import error, request


class LocalInferenceError(RuntimeError):
    """Raised when the local inference backend is unavailable or invalid."""


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
        return cls(
            base_url=os.environ.get("COGNITIVE_OS_LLM_BASE_URL", "http://127.0.0.1:8000/v1").rstrip("/"),
            model=os.environ.get("COGNITIVE_OS_LLM_MODEL", "local"),
            timeout_seconds=float(os.environ.get("COGNITIVE_OS_LLM_TIMEOUT", "20")),
            response_format=os.environ.get("COGNITIVE_OS_LLM_RESPONSE_FORMAT", "1").lower() in {"1", "true", "yes", "on"},
            api_key=os.environ.get("COGNITIVE_OS_LLM_API_KEY") or None,
            provider_label=os.environ.get("COGNITIVE_OS_LLM_PROVIDER", "local"),
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
        start = content.find("{")
        end = content.rfind("}")
        if start < 0 or end <= start:
            raise
        result = json.loads(content[start : end + 1])
    if not isinstance(result, dict):
        raise LocalInferenceError("local inference response must decode to object")
    return result
