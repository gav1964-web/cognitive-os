"""Generic dispatcher for configured artifact builders."""

from __future__ import annotations

import importlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_BUILDERS_PATH = ROOT / "config" / "artifact_builders.json"


class ArtifactBuilderError(RuntimeError):
    """Raised when a configured artifact builder cannot run safely."""


@lru_cache(maxsize=1)
def load_artifact_builders(path: str | None = None) -> dict[str, dict[str, Any]]:
    source = Path(path) if path else ARTIFACT_BUILDERS_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "artifact_builders.v1":
        raise ArtifactBuilderError("artifact builders must use schema_version artifact_builders.v1")
    builders = payload.get("builders")
    if not isinstance(builders, dict):
        raise ArtifactBuilderError("artifact builders must contain builders object")
    normalized = {}
    for builder_id, config in builders.items():
        if not isinstance(config, dict):
            raise ArtifactBuilderError(f"builder config must be object: {builder_id}")
        for field in ("callable", "artifact_type", "role_id"):
            if not config.get(field):
                raise ArtifactBuilderError(f"builder {builder_id} requires {field}")
        normalized[str(builder_id)] = dict(config)
    return normalized


def build_configured_artifact(*, builder_id: str, **kwargs: Any) -> dict[str, Any]:
    builders = load_artifact_builders()
    if builder_id not in builders:
        raise ArtifactBuilderError(f"unknown artifact builder: {builder_id}")
    config = builders[builder_id]
    function = _load_callable(str(config["callable"]))
    artifact = function(**kwargs)
    if not isinstance(artifact, dict):
        raise ArtifactBuilderError(f"builder returned non-object artifact: {builder_id}")
    artifact_type = str(config["artifact_type"])
    role_id = str(config["role_id"])
    if artifact.get("artifact_type") != artifact_type:
        raise ArtifactBuilderError(
            f"builder {builder_id} returned artifact_type {artifact.get('artifact_type')} instead of {artifact_type}"
        )
    if artifact.get("role") != role_id:
        raise ArtifactBuilderError(f"builder {builder_id} returned role {artifact.get('role')} instead of {role_id}")
    return artifact


def _load_callable(spec: str) -> Callable[..., Any]:
    if ":" not in spec:
        raise ArtifactBuilderError(f"callable must be module:function: {spec}")
    module_name, function_name = spec.split(":", 1)
    module = importlib.import_module(module_name)
    function = getattr(module, function_name, None)
    if not callable(function):
        raise ArtifactBuilderError(f"configured builder is not callable: {spec}")
    return function
