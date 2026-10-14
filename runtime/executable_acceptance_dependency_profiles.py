"""Dependency profile modules for executable acceptance callable loading."""

from __future__ import annotations

import importlib.metadata as importlib_metadata
import importlib.util
import sys
import types
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .executable_acceptance_materializers import materialize
from .executable_acceptance_policy import dependency_stub_policy


def can_profile_module(missing: str, policy: dict[str, Any], profiled: list[str]) -> bool:
    if not policy.get("generated_module_profiles_enabled") or not missing or missing in profiled:
        return False
    profiles = dict(policy.get("generated_module_profiles") or {})
    return missing in profiles


def preinstall_profile_modules(
    project_dir: Path,
    module_name: str,
    policy: dict[str, Any],
    profiled: list[str],
) -> list[str]:
    if not policy.get("generated_module_profiles_enabled") or not module_name:
        return []
    created: list[str] = []
    top = module_name.split(".", 1)[0]
    for name in dict(policy.get("generated_module_profiles") or {}):
        if name in sys.modules or name in profiled or name.split(".", 1)[0] != top:
            continue
        if profile_module_file_exists(project_dir, name):
            continue
        if (project_dir / top).is_dir() or (project_dir / "src" / top).is_dir():
            continue
        created.extend(install_profile_module(name, policy))
        profiled.append(name)
    return created


def discard_synthetic_local_parent(project_dir: Path, missing: str, created: list[str]) -> None:
    top = missing.split(".", 1)[0]
    if top not in created:
        return
    if (project_dir / top).is_dir() or (project_dir / "src" / top).is_dir():
        sys.modules.pop(top, None)


def profile_module_file_exists(project_dir: Path, name: str) -> bool:
    parts = name.split(".")
    relative = Path(*parts)
    candidates = [project_dir / relative.with_suffix(".py"), project_dir / "src" / relative.with_suffix(".py")]
    return any(path.exists() for path in candidates)


def install_profile_module(name: str, policy: dict[str, Any]) -> list[str]:
    created: list[str] = []
    parts = name.split(".")
    for index in range(1, len(parts)):
        parent_name = ".".join(parts[:index])
        if parent_name not in sys.modules:
            parent = types.ModuleType(parent_name)
            parent.__path__ = []
            parent.__file__ = f"<dependency-profile:{parent_name}>"
            parent.__spec__ = importlib.util.spec_from_loader(parent_name, loader=None, is_package=True)
            sys.modules[parent_name] = parent
            created.append(parent_name)
        if index > 1:
            setattr(sys.modules[".".join(parts[: index - 1])], parts[index - 1], sys.modules[parent_name])
    module = types.ModuleType(name)
    module.__file__ = f"<dependency-profile:{name}>"
    module.__spec__ = importlib.util.spec_from_loader(name, loader=None, is_package=False)
    attrs = dict(dict(policy.get("generated_module_profiles") or {}).get(name, {}).get("attrs") or {})
    for key, value in attrs.items():
        setattr(module, str(key), profile_attr_value(value))
    sys.modules[name] = module
    parent_name, _, child_name = name.rpartition(".")
    parent = sys.modules.get(parent_name)
    if parent is not None:
        setattr(parent, child_name, module)
    return [*created, name]


def profile_attr_value(value: Any) -> Any:
    if isinstance(value, dict) and value.get("__fixture__") == "callable_empty_string":
        return lambda *args, **kwargs: ""
    return materialize(value)


@contextmanager
def dependency_metadata_context(policy: dict[str, Any]):
    packages = {str(item).replace("-", "_").lower() for item in policy.get("metadata_packages", [])}
    used: list[str] = []
    if not policy.get("metadata_profiles_enabled") or not packages:
        yield used
        return
    default_version = str(policy.get("metadata_default_version") or "0.0.0")
    original_version = importlib_metadata.version
    original_metadata = importlib_metadata.metadata
    original_distribution = importlib_metadata.distribution

    def normalize(name: str) -> str:
        return str(name).replace("-", "_").lower()

    def remember(name: str) -> str:
        normalized = normalize(name)
        if normalized in packages and normalized not in used:
            used.append(normalized)
        return normalized

    def version(name: str) -> str:
        return default_version if remember(name) in packages else original_version(name)

    def metadata(name: str) -> dict[str, str]:
        return {"Name": str(name), "Version": default_version} if remember(name) in packages else original_metadata(name)

    def distribution(name: str) -> "_StubDistribution":
        return _StubDistribution(str(name), default_version) if remember(name) in packages else original_distribution(name)

    importlib_metadata.version = version
    importlib_metadata.metadata = metadata
    importlib_metadata.distribution = distribution
    try:
        yield used
    finally:
        importlib_metadata.version = original_version
        importlib_metadata.metadata = original_metadata
        importlib_metadata.distribution = original_distribution


class _StubDistribution:
    def __init__(self, name: str, version: str):
        self.metadata = {"Name": name, "Version": version}
        self.version = version

    def read_text(self, name: str) -> str:
        return ""


def install_dependency_profile_modules(names: list[str]) -> list[str]:
    policy = dependency_stub_policy()
    return [created for name in names for created in install_profile_module(str(name), policy)]
