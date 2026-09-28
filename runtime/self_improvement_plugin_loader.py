"""Load configured self-improvement plugins through a narrow contract."""

from __future__ import annotations

import importlib
import inspect
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable


DEFAULT_PATH = Path(__file__).resolve().parents[1] / "config" / "self_improvement_plugins.json"
ENTRYPOINT_PREFIX = "runtime.improvement_plugins."


class ImprovementPluginError(RuntimeError):
    """Raised when an improvement plugin declaration is unsafe or invalid."""


@lru_cache(maxsize=1)
def load_improvement_plugin_catalog(path: str | None = None) -> dict[str, Any]:
    source = Path(path) if path else DEFAULT_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "self_improvement_plugins.v1":
        raise ImprovementPluginError("self-improvement plugins schema mismatch")
    plugins = payload.get("plugins")
    if not isinstance(plugins, list):
        raise ImprovementPluginError("self-improvement plugins must contain a plugins list")
    seen: set[str] = set()
    for plugin in plugins:
        _validate_plugin(dict(plugin or {}), seen)
    cycle = dict(payload.get("cycle") or {})
    if int(cycle.get("max_plugins_per_failure") or 0) <= 0:
        raise ImprovementPluginError("plugin cycle requires a positive plugin limit")
    if cycle.get("runtime_patch_auto_promotion") is not False:
        raise ImprovementPluginError("runtime patch auto-promotion must remain disabled")
    return payload


def enabled_improvement_plugins(path: str | None = None) -> list[dict[str, Any]]:
    payload = load_improvement_plugin_catalog(path)
    rows = [dict(row) for row in payload["plugins"] if row.get("enabled")]
    return sorted(rows, key=lambda row: (int(row.get("priority") or 100), str(row["id"])))


def load_improvement_entrypoint(entrypoint: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    if not entrypoint.startswith(ENTRYPOINT_PREFIX) or ":" not in entrypoint:
        raise ImprovementPluginError(f"unsafe improvement plugin entrypoint: {entrypoint}")
    module_name, function_name = entrypoint.split(":", 1)
    fn = getattr(importlib.import_module(module_name), function_name, None)
    if not callable(fn):
        raise ImprovementPluginError(f"improvement plugin entrypoint is not callable: {entrypoint}")
    params = list(inspect.signature(fn).parameters.values())
    if len(params) != 1 or params[0].kind not in {
        inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD,
    }:
        raise ImprovementPluginError(f"improvement plugin must accept one context: {entrypoint}")
    return fn


def _validate_plugin(plugin: dict[str, Any], seen: set[str]) -> None:
    plugin_id = str(plugin.get("id") or "")
    if not re.fullmatch(r"[a-z][a-z0-9_]*", plugin_id) or plugin_id in seen:
        raise ImprovementPluginError(f"invalid or duplicate improvement plugin id: {plugin_id}")
    seen.add(plugin_id)
    if not re.fullmatch(r"\d+\.\d+\.\d+", str(plugin.get("version") or "")):
        raise ImprovementPluginError(f"invalid improvement plugin version: {plugin_id}")
    entrypoint = str(plugin.get("entrypoint") or "")
    if not entrypoint.startswith(ENTRYPOINT_PREFIX) or ":" not in entrypoint:
        raise ImprovementPluginError(f"unsafe improvement plugin entrypoint: {plugin_id}")
    if not plugin.get("change_types"):
        raise ImprovementPluginError(f"improvement plugin requires change types: {plugin_id}")
