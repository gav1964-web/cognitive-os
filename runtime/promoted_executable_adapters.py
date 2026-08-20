"""Validated executable-acceptance adapters promoted from repeated evidence."""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path
from typing import Any


DEFAULT_PATH = Path(__file__).resolve().parents[1] / "knowledge" / "role_knowledge" / "promoted_executable_adapters.json"
_OVERRIDE: ContextVar[list[dict[str, Any]] | None] = ContextVar("executable_adapter_override", default=None)
_MODULE = re.compile(r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*$")
_SAFE_FIXTURES = {
    "callable_empty_list", "callable_empty_string", "callable_identity", "callable_noop",
    "callable_transport_result", "callable_true", "module_getattr_stub", "safe_method_attribute",
    "safe_symbolic_attribute", "stub_class",
}


@lru_cache(maxsize=4)
def load_executable_adapters(path: str | None = None) -> dict[str, Any]:
    payload = json.loads(Path(path or DEFAULT_PATH).read_text(encoding="utf-8"))
    if payload.get("schema_version") != "promoted_executable_adapters.v1":
        raise ValueError("promoted executable adapters schema mismatch")
    adapters = payload.get("adapters")
    if not isinstance(adapters, list):
        raise ValueError("promoted executable adapters must contain adapters list")
    seen: set[str] = set()
    modules: set[str] = set()
    for value in adapters:
        adapter = validate_executable_adapter(dict(value or {}))
        if adapter["id"] in seen:
            raise ValueError(f"duplicate promoted executable adapter: {adapter['id']}")
        if adapter["module"] in modules:
            raise ValueError(f"duplicate promoted executable adapter module: {adapter['module']}")
        seen.add(adapter["id"])
        modules.add(adapter["module"])
    return payload


def validate_executable_adapter(value: dict[str, Any]) -> dict[str, Any]:
    adapter_id = str(value.get("id") or "")
    module = str(value.get("module") or "")
    allowed = {"id", "kind", "module", "profile", "activation", "promotion_evidence"}
    if set(value) - allowed:
        raise ValueError(f"unknown executable adapter fields: {adapter_id}")
    if not adapter_id or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,120}", adapter_id):
        raise ValueError("invalid executable adapter id")
    if value.get("kind") != "generated_module_profile":
        raise ValueError("invalid executable adapter identity or kind")
    root = module.split(".", 1)[0]
    if not _MODULE.fullmatch(module) or root in sys.stdlib_module_names or module.startswith(("runtime", "tests", "knowledge")):
        raise ValueError(f"invalid executable adapter module: {module}")
    if value.get("activation") != "acceptance_sandbox_only":
        raise ValueError(f"unsafe executable adapter activation: {adapter_id}")
    profile = dict(value.get("profile") or {})
    if set(profile) != {"attrs"}:
        raise ValueError(f"invalid executable adapter profile shape: {adapter_id}")
    attrs = profile.get("attrs")
    if not isinstance(attrs, dict) or not attrs or len(attrs) > 24:
        raise ValueError(f"executable adapter attrs required or excessive: {adapter_id}")
    _validate_payload(attrs, depth=0)
    return value


def _validate_payload(value: Any, *, depth: int) -> None:
    if depth > 5:
        raise ValueError("executable adapter payload nesting is excessive")
    if value is None or isinstance(value, (bool, int, float)):
        return
    if isinstance(value, str):
        if len(value) > 400:
            raise ValueError("executable adapter string is excessive")
        return
    if isinstance(value, list):
        if len(value) > 32:
            raise ValueError("executable adapter list is excessive")
        for item in value:
            _validate_payload(item, depth=depth + 1)
        return
    if not isinstance(value, dict) or len(value) > 32:
        raise ValueError("invalid executable adapter payload")
    forbidden = {"code", "source", "replacement_source", "diff", "entrypoint"}
    if forbidden & set(value):
        raise ValueError("raw executable content is forbidden in adapters")
    fixture = value.get("__fixture__")
    if fixture is not None and fixture not in _SAFE_FIXTURES:
        raise ValueError(f"unsafe executable adapter fixture: {fixture}")
    for key, item in value.items():
        if not isinstance(key, str) or (key.startswith("__") and key != "__fixture__"):
            raise ValueError("invalid executable adapter attribute")
        _validate_payload(item, depth=depth + 1)


def generated_module_profiles() -> dict[str, Any]:
    adapters = _OVERRIDE.get()
    if adapters is None:
        adapters = list(load_executable_adapters()["adapters"])
    return {str(row["module"]): dict(row["profile"]) for row in adapters}


@contextmanager
def temporary_executable_adapters(adapters: list[dict[str, Any]]):
    checked = [validate_executable_adapter(dict(row)) for row in adapters]
    active = [dict(row) for row in load_executable_adapters()["adapters"]]
    by_id = {str(row["id"]): row for row in [*active, *checked]}
    token = _OVERRIDE.set(list(by_id.values()))
    try:
        yield
    finally:
        _OVERRIDE.reset(token)


def promote_executable_adapter(*, root: Path, adapter: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    checked = validate_executable_adapter(dict(adapter))
    path = root / "knowledge" / "role_knowledge" / "promoted_executable_adapters.json"
    payload = load_executable_adapters(str(path))
    if any(str(row.get("id")) == checked["id"] for row in payload["adapters"]):
        return {"status": "already_promoted", "adapter_id": checked["id"], "path": path.as_posix()}
    record = {**checked, "promotion_evidence": evidence}
    candidate = {**payload, "adapters": sorted([*payload["adapters"], record], key=lambda row: str(row["id"]))}
    _validate_candidate(candidate)
    _atomic_write(path, candidate)
    load_executable_adapters.cache_clear()
    return {"status": "promoted", "adapter_id": checked["id"], "path": path.as_posix()}


def _validate_candidate(payload: dict[str, Any]) -> None:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
        json.dump(payload, handle, ensure_ascii=False)
        temporary = Path(handle.name)
    try:
        load_executable_adapters.cache_clear()
        load_executable_adapters(str(temporary))
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(encoded)
        temporary = Path(handle.name)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
