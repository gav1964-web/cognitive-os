"""Config-backed policy helpers for executable acceptance samples."""

from __future__ import annotations

import json
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "config" / "executable_acceptance_policy.json"
_OVERRIDE: ContextVar[dict[str, Any] | None] = ContextVar("executable_acceptance_policy_override", default=None)


def load_executable_acceptance_policy(path: str | Path | None = None) -> dict[str, Any]:
    source = Path(path or DEFAULT_PATH)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "executable_acceptance_policy.v1":
        raise ValueError("Unsupported executable acceptance policy schema")
    return payload


def _policy() -> dict[str, Any]:
    return _OVERRIDE.get() or _cached_policy()


@lru_cache(maxsize=1)
def _cached_policy() -> dict[str, Any]:
    return load_executable_acceptance_policy()


def clear_executable_acceptance_policy_cache() -> None:
    _cached_policy.cache_clear()


@contextmanager
def temporary_executable_acceptance_policy(policy: dict[str, Any]):
    if policy.get("schema_version") != "executable_acceptance_policy.v1":
        raise ValueError("Unsupported temporary executable acceptance policy schema")
    token = _OVERRIDE.set(policy)
    try:
        yield
    finally:
        _OVERRIDE.reset(token)


def external_call_tokens() -> tuple[str, ...]:
    dependency = dict(_policy().get("dependency_policy") or {})
    return tuple(str(item) for item in dependency.get("external_call_tokens", []) if item)


def dependency_stub_policy() -> dict[str, Any]:
    dependency = dict(_policy().get("dependency_policy") or {})
    stubs = dict(dependency.get("controlled_stubs") or {})
    metadata = dict(dependency.get("metadata_profiles") or {})
    generated = dict(dependency.get("generated_module_profiles") or {})
    return {
        "enabled": bool(stubs.get("enabled")),
        "max_missing_modules": int(stubs.get("max_missing_modules") or 0),
        "pre_stub_modules": tuple(str(item) for item in stubs.get("pre_stub_modules", []) if item),
        "stub_external_missing_modules": bool(stubs.get("stub_external_missing_modules")),
        "stub_object_features": tuple(str(item) for item in stubs.get("stub_object_features", []) if item),
        "metadata_profiles_enabled": bool(metadata.get("enabled")),
        "metadata_default_version": str(metadata.get("default_version") or "0.0.0"),
        "metadata_packages": tuple(str(item) for item in metadata.get("packages", []) if item),
        "generated_module_profiles_enabled": bool(generated.get("enabled")),
        "generated_module_profiles": dict(generated.get("modules") or {}),
    }


def method_fixture_policy() -> dict[str, Any]:
    policy = dict(_policy().get("method_fixture_policy") or {})
    return {
        "enabled": bool(policy.get("enabled")),
        "safe_uninitialized_instance": bool(policy.get("safe_uninitialized_instance")),
        "default_constructor_first": bool(policy.get("default_constructor_first")),
        "local_import_stub_functions": tuple(str(item) for item in policy.get("local_import_stub_functions", []) if item),
        "local_import_stub_methods": tuple(str(item) for item in policy.get("local_import_stub_methods", []) if item),
        "instance_attribute_profiles": dict(policy.get("instance_attribute_profiles") or {}),
        "recipes": dict(policy.get("recipes") or {}),
    }


def source_isolation_policy() -> dict[str, Any]:
    policy = dict(_policy().get("source_isolation_policy") or {})
    return {
        "effect_module_stubs": dict(policy.get("effect_module_stubs") or {}),
        "framework_contexts": _clone(dict(policy.get("framework_contexts") or {})),
        "global_factory_fixtures": dict(policy.get("global_factory_fixtures") or {}),
        "local_import_factory_fixtures": _clone(dict(policy.get("local_import_factory_fixtures") or {})),
        "global_symbol_fixtures": dict(policy.get("global_symbol_fixtures") or {}),
    }


def structural_sample_policy() -> dict[str, Any]:
    return _clone(dict(_policy().get("structural_sample_policy") or {}))


def target_path_resolution_policy() -> dict[str, Any]:
    policy = dict(_policy().get("target_path_resolution") or {})
    return {
        "enabled": bool(policy.get("enabled")),
        "max_candidate_files": max(1, int(policy.get("max_candidate_files") or 1)),
        "max_unique_matches": max(1, int(policy.get("max_unique_matches") or 1)),
        "ignored_directories": tuple(str(item) for item in policy.get("ignored_directories", []) if item),
    }


def execution_context_policy() -> dict[str, Any]:
    policy = dict(_policy().get("execution_context") or {})
    return {
        "isolate_process_arguments": bool(policy.get("isolate_process_arguments")),
        "program_name": str(policy.get("program_name") or "acceptance-probe"),
    }


def skipped_recovery_hint(reason: str) -> str:
    recovery = dict(_policy().get("skipped_recovery") or {})
    return str(recovery.get(reason) or "")


def sample_value(type_name: str, field_name: str = "", *, signature_mode: bool = False) -> Any:
    samples = dict(_policy().get("sample_values") or {})
    field = field_name.lower()
    lowered = type_name.lower()
    field_values = dict(samples.get("field_values") or {})
    if field in field_values:
        return _clone(field_values[field])
    if field in set(samples.get("nullable_fields") or []):
        return None
    if field in set(samples.get("optional_nullable_fields") or []) and ("none" in lowered or "optional" in lowered):
        return None
    for prefix, value in dict(samples.get("field_prefix_values") or {}).items():
        if field.startswith(str(prefix)):
            return _clone(value)
    fixture = _fixture_for(samples, field, lowered)
    if fixture:
        return {"__fixture__": fixture}
    type_rules = dict(samples.get("signature_type_contains" if signature_mode else "type_contains") or {})
    for token, value in type_rules.items():
        if str(token) in lowered:
            return _clone(value)
    return _clone(samples.get("default", "sample"))


def _fixture_for(samples: dict[str, Any], field: str, lowered_type: str) -> str:
    fixtures = dict(samples.get("fixture_fields") or {})
    if field in fixtures:
        return str(fixtures[field])
    field_types = dict(dict(samples.get("fixture_field_type_contains") or {}).get(field) or {})
    for token, fixture in field_types.items():
        if str(token) in lowered_type:
            return str(fixture)
    for token, fixture in dict(samples.get("fixture_type_contains") or {}).items():
        if str(token) in lowered_type:
            return str(fixture)
    return ""


def _clone(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))
