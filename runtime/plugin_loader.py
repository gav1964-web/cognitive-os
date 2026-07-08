"""Explicit plugin metadata loader.

The loader reads manifests and schemas, but imports plugin code only when a node
is actually executed.
"""

from __future__ import annotations

import importlib
import inspect
import json
import re
from pathlib import Path
from typing import Any, Callable

from .integrity import hash_plugin_dir
from .models import Capability
from .plugin_lint import lint_plugin
from .schema import validate_payload


class PluginLoadError(RuntimeError):
    """Raised when plugin metadata is inconsistent."""


def load_capabilities(root: Path) -> dict[str, Capability]:
    plugins_dir = root / "plugins"
    capabilities: dict[str, Capability] = {}
    for manifest_path in sorted(plugins_dir.glob("*/plugin.json")):
        manifest = _read_json(manifest_path)
        plugin_dir = manifest_path.parent
        _validate_manifest_shape(manifest_path, manifest)
        plugin_id = str(manifest["id"])
        if plugin_id != plugin_dir.name:
            raise PluginLoadError(f"plugin id must match directory name: {plugin_id} != {plugin_dir.name}")
        if plugin_id in capabilities:
            raise PluginLoadError(f"duplicate plugin id: {plugin_id}")
        input_schema_ref = plugin_dir / "schemas" / "input.json"
        output_schema_ref = plugin_dir / "schemas" / "output.json"
        input_schema = _read_json(input_schema_ref)
        output_schema = _read_json(output_schema_ref)
        _validate_schema_shape(plugin_id, "input", input_schema)
        _validate_schema_shape(plugin_id, "output", output_schema)
        _validate_entrypoint(plugin_id, str(manifest["entrypoint"]))
        side_effects = _validate_side_effects(plugin_id, dict(manifest.get("side_effects", {})))
        try:
            lint_plugin(plugin_dir, plugin_id, side_effects=side_effects)
        except Exception as exc:
            raise PluginLoadError(str(exc)) from exc
        capability = Capability(
            id=plugin_id,
            version=str(manifest["version"]),
            entrypoint=str(manifest["entrypoint"]),
            input_schema_ref=_rel(root, input_schema_ref),
            output_schema_ref=_rel(root, output_schema_ref),
            input_schema=input_schema,
            output_schema=output_schema,
            determinism_grade=str(manifest.get("determinism_grade", "C")),
            side_effects=side_effects,
            lifecycle_status=str(manifest.get("lifecycle_status", "active")),
            version_hash=hash_plugin_dir(plugin_dir),
            fallback_for=[str(item) for item in manifest.get("fallback_for", [])],
        )
        _validate_lifecycle_status(capability.id, capability.lifecycle_status)
        capabilities[capability.id] = capability
    _validate_fallback_targets(capabilities)
    return capabilities


def load_entrypoint(entrypoint: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    importlib.invalidate_caches()
    module_name, function_name = entrypoint.split(":", 1)
    module = importlib.import_module(module_name)
    fn = getattr(module, function_name)
    if not callable(fn):
        raise TypeError(f"entrypoint is not callable: {entrypoint}")
    _validate_entrypoint_signature(entrypoint, fn)
    return fn


def validate_capability_contract(capability: Capability) -> None:
    validate_payload({}, {"type": "object"}, label=f"{capability.id}.contract_probe")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise PluginLoadError(f"missing required file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _rel(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _validate_manifest_shape(path: Path, manifest: dict[str, Any]) -> None:
    for key in ("id", "version", "entrypoint", "determinism_grade", "side_effects", "lifecycle_status"):
        if not str(manifest.get(key, "")).strip():
            raise PluginLoadError(f"{path} missing required key: {key}")
    if not re.match(r"^\d+\.\d+\.\d+$", str(manifest["version"])):
        raise PluginLoadError(f"{path} version must use semver MAJOR.MINOR.PATCH")
    if str(manifest["determinism_grade"]) not in {"A", "B", "C", "D", "E"}:
        raise PluginLoadError(f"{path} invalid determinism_grade")


def _validate_schema_shape(plugin_id: str, schema_name: str, schema: dict[str, Any]) -> None:
    if schema.get("type") != "object":
        raise PluginLoadError(f"{plugin_id} {schema_name} schema must be object schema")
    if not isinstance(schema.get("properties", {}), dict):
        raise PluginLoadError(f"{plugin_id} {schema_name} schema properties must be object")
    if not isinstance(schema.get("required", []), list):
        raise PluginLoadError(f"{plugin_id} {schema_name} schema required must be list")
    if schema.get("additionalProperties") is not False:
        raise PluginLoadError(f"{plugin_id} {schema_name} schema must set additionalProperties=false")


def _validate_entrypoint(plugin_id: str, entrypoint: str) -> None:
    prefix = f"plugins.{plugin_id}.src."
    if ":" not in entrypoint:
        raise PluginLoadError(f"{plugin_id} entrypoint must use module:function syntax")
    module_name, function_name = entrypoint.split(":", 1)
    if not module_name.startswith(prefix):
        raise PluginLoadError(f"{plugin_id} entrypoint must stay inside plugin src package")
    if not function_name:
        raise PluginLoadError(f"{plugin_id} entrypoint function is empty")


def _validate_side_effects(plugin_id: str, side_effects: dict[str, Any]) -> dict[str, Any]:
    allowed_filesystem = {"none", "read_only", "write_scoped"}
    allowed_network = {"none", "allowlist"}
    allowed_secrets = {"none", "declared"}
    filesystem = str(side_effects.get("filesystem", "none"))
    network = str(side_effects.get("network", "none"))
    secrets = str(side_effects.get("secrets", "none"))
    if filesystem not in allowed_filesystem:
        raise PluginLoadError(f"{plugin_id} invalid filesystem side effect: {filesystem}")
    if network not in allowed_network:
        raise PluginLoadError(f"{plugin_id} invalid network side effect: {network}")
    if secrets not in allowed_secrets:
        raise PluginLoadError(f"{plugin_id} invalid secrets side effect: {secrets}")
    return {"filesystem": filesystem, "network": network, "secrets": secrets}


def _validate_lifecycle_status(plugin_id: str, status: str) -> None:
    if status not in {"active", "degraded", "quarantined", "rebuilding", "retired"}:
        raise PluginLoadError(f"{plugin_id} invalid lifecycle status: {status}")


def _validate_fallback_targets(capabilities: dict[str, Capability]) -> None:
    for capability in capabilities.values():
        for target in capability.fallback_for:
            if target not in capabilities:
                raise PluginLoadError(f"{capability.id} fallback target does not exist: {target}")


def _validate_entrypoint_signature(entrypoint: str, fn: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
    signature = inspect.signature(fn)
    params = list(signature.parameters.values())
    if len(params) != 1:
        raise TypeError(f"entrypoint must accept exactly one payload parameter: {entrypoint}")
    if params[0].kind not in {inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY}:
        raise TypeError(f"entrypoint payload parameter has invalid kind: {entrypoint}")
