"""Shard-pass cache helpers for native pytest intake."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any

from .project_native_failure_process import _project_digest

def _shard_cache_key(
    project: Path, nodeids: list[str], intake: dict[str, Any], *, mode: str
) -> str | None:
    if not bool(intake.get("shard_cache_enabled", True)) or not intake.get("shard_cache_path"):
        return None
    project_cache = intake.setdefault("_shard_project_digests", {})
    project_key = str(project.resolve())
    if project_key not in project_cache:
        project_cache[project_key] = _project_digest(project)
    if "_shard_environment_digest" not in intake:
        overlay_digest = _configured_overlay_digest(intake.get("dependency_overlay_path"))
        tool_overlay_digest = _configured_overlay_digest(intake.get("tool_overlay_path"))
        environment = {
            "python": sys.version,
            "platform": platform.platform(),
            "overlay": overlay_digest,
            "tool_overlay": tool_overlay_digest,
        }
        intake["_shard_environment_digest"] = hashlib.sha256(
            json.dumps(environment, sort_keys=True).encode("utf-8")
        ).hexdigest()
    payload = {
        "schema": "native_shard_pass.v1",
        "mode": mode,
        "project_digest": project_cache[project_key],
        "environment_digest": intake["_shard_environment_digest"],
        "pytest_arguments": list(intake.get("pytest_arguments") or []),
        "nodeids": nodeids,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

def _configured_overlay_digest(value: Any) -> str:
    if not value:
        return "none"
    overlay = Path(str(value))
    return _project_digest(overlay) if overlay.is_dir() else "none"

def _load_cached_shard_pass(cache_key: str, intake: dict[str, Any]) -> bool:
    path = Path(str(intake["shard_cache_path"])) / f"{cache_key}.json"
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return bool(
        record.get("schema_version") == "native_shard_pass.v1"
        and record.get("cache_key") == cache_key
        and record.get("status") == "passed"
    )

def _store_cached_shard_pass(
    cache_key: str, intake: dict[str, Any], nodeids: list[str], *, mode: str
) -> None:
    directory = Path(str(intake["shard_cache_path"]))
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{cache_key}.json"
    record = {
        "schema_version": "native_shard_pass.v1",
        "cache_key": cache_key,
        "status": "passed",
        "mode": mode,
        "nodeid_count": len(nodeids),
    }
    temporary = path.with_suffix(f".tmp-{os.getpid()}")
    temporary.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)
