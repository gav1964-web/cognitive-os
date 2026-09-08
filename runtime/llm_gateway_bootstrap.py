"""Ensure the configured local LLM gateway is ready before Cognitive OS runs."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import ProxyHandler, build_opener

SCHEMA_VERSION = "llm_gateway_bootstrap.v1"


def ensure_llm_gateway_for_url(root: Path, base_url: str) -> dict[str, Any]:
    """Bootstrap the managed gateway only for a loopback LLM endpoint."""
    endpoint = urlparse(base_url)
    host = (endpoint.hostname or "").lower()
    if host not in {"127.0.0.1", "localhost", "::1"}:
        return _result("not_required", checked=False, base_url=base_url)
    config_path = root / "config" / "llm_gateway_bootstrap.json"
    if config_path.is_file():
        try:
            managed = urlparse(str(_load_policy(config_path).get("base_url") or ""))
        except (OSError, ValueError, json.JSONDecodeError):
            return ensure_llm_gateway(root)
        if _origin(endpoint) != _origin(managed):
            return _result("not_required", checked=False, base_url=base_url)
    return ensure_llm_gateway(root)


def _origin(parsed: Any) -> tuple[str, str, int | None]:
    return parsed.scheme.lower(), (parsed.hostname or "").lower(), parsed.port


def ensure_llm_gateway(root: Path) -> dict[str, Any]:
    config_path = root / "config" / "llm_gateway_bootstrap.json"
    if not config_path.is_file():
        return _result("not_configured", checked=False)
    try:
        policy = _load_policy(config_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _result("failed", error=f"invalid bootstrap config: {exc}")
    if not policy.get("enabled"):
        return _result("disabled", checked=False)

    health_url = _health_url(policy)
    request_timeout = float(policy.get("request_timeout_seconds") or 2.0)
    if _health_ready(health_url, request_timeout):
        return _result("already_running", health_url=health_url)

    resolved = _resolved_launch(root, policy)
    if resolved.get("error"):
        return _result("failed", health_url=health_url, error=resolved["error"])
    try:
        process = _launch_gateway(resolved)
    except OSError as exc:
        return _result("failed", health_url=health_url, error=f"gateway start failed: {exc}")

    deadline = time.monotonic() + float(policy.get("startup_timeout_seconds") or 30.0)
    interval = float(policy.get("poll_interval_seconds") or 0.5)
    while time.monotonic() < deadline:
        if _health_ready(health_url, request_timeout):
            return _result(
                "started", health_url=health_url, pid=process.pid,
                log_path=resolved["log_path"].as_posix(),
            )
        exit_code = process.poll()
        if exit_code is not None:
            return _result(
                "failed", health_url=health_url, pid=process.pid,
                log_path=resolved["log_path"].as_posix(),
                error=f"gateway exited before readiness with code {exit_code}",
            )
        time.sleep(max(0.05, interval))
    return _result(
        "failed", health_url=health_url, pid=process.pid,
        log_path=resolved["log_path"].as_posix(),
        error="gateway readiness timeout",
    )


def _load_policy(path: Path) -> dict[str, Any]:
    policy = json.loads(path.read_text(encoding="utf-8"))
    if policy.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
    return policy


def _health_url(policy: dict[str, Any]) -> str:
    base = str(policy.get("base_url") or "").rstrip("/")
    path = "/" + str(policy.get("health_path") or "health").lstrip("/")
    return base + path


def _health_ready(url: str, timeout: float) -> bool:
    opener = build_opener(ProxyHandler({}))
    try:
        with opener.open(url, timeout=timeout) as response:
            return int(response.status) == 200
    except (HTTPError, URLError, OSError, TimeoutError):
        return False


def _resolved_launch(root: Path, policy: dict[str, Any]) -> dict[str, Any]:
    project_dir = (root / str(policy.get("project_dir") or "")).resolve()
    executable = (project_dir / str(policy.get("python_executable") or "")).resolve()
    command = [str(item) for item in policy.get("command", []) if str(item)]
    log_path = (root / str(policy.get("log_path") or "artifacts/runtime/llm_gateway.log")).resolve()
    if not project_dir.is_dir():
        return {"error": f"gateway project not found: {project_dir}"}
    if not executable.is_file():
        return {"error": f"gateway Python not found: {executable}"}
    if not command:
        return {"error": "gateway command is empty"}
    return {
        "project_dir": project_dir,
        "executable": executable,
        "command": command,
        "log_path": log_path,
    }


def _launch_gateway(resolved: dict[str, Any]) -> subprocess.Popen[Any]:
    log_path = Path(resolved["log_path"])
    log_path.parent.mkdir(parents=True, exist_ok=True)
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    with log_path.open("a", encoding="utf-8") as log_file:
        return subprocess.Popen(
            [str(resolved["executable"]), *resolved["command"]],
            cwd=str(resolved["project_dir"]),
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
            start_new_session=os.name != "nt",
        )


def _result(status: str, *, checked: bool = True, **fields: Any) -> dict[str, Any]:
    return {
        "artifact_type": "LLMGatewayBootstrapResult",
        "status": status,
        "checked": checked,
        **{key: value for key, value in fields.items() if value not in (None, "")},
    }
