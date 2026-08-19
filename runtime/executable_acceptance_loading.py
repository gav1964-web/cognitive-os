"""Callable loading helpers for executable acceptance harness analysis."""

from __future__ import annotations

import ast
import importlib
import importlib.metadata as importlib_metadata
import importlib.util
import sys
import types
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .executable_acceptance_isolation import load_source_isolated_callable
from .executable_acceptance_materializers import materialize
from .executable_acceptance_policy import dependency_stub_policy
from .python_parser_compatibility import parse_compatible_source

def load_supported_callable(project_dir: Path, path_text: str, symbol: str, path: Path) -> dict[str, Any]:
    if _has_unbounded_top_level_loop(path):
        isolated = load_source_isolated_callable(path, symbol)
        if not isolated.get("reason"):
            isolated["source_isolated"] = True
            return isolated
    module_name = module_name_from_path(path_text)
    if module_name:
        try:
            with fresh_import(module_name):
                before_modules = set(sys.modules)
                loaded = _import_module_with_optional_stubs(project_dir, module_name)
                module = loaded["module"]
                func = getattr(module, symbol, None)
                if _is_stub_object(func) and len(Path(path_text).parts) > 1:
                    if isolated := _isolated_with_loaded(path, symbol, loaded):
                        return isolated
                    func = None
                if func is not None or len(Path(path_text).parts) > 1:
                    return {
                        "callable": func,
                        "module": module,
                        "reason": "" if func is not None else "target_not_callable",
                        "dependency_stubs": loaded.get("dependency_stubs", []),
                        "dependency_stub_modules_created": loaded.get("dependency_stub_modules_created", []),
                        "dependency_metadata_profiles": loaded.get("dependency_metadata_profiles", []),
                        "dependency_module_profiles": loaded.get("dependency_module_profiles", []),
                    }
        except (Exception, SystemExit) as exc:
            _remove_new_modules(locals().get("before_modules", set()))
            if len(Path(path_text).parts) > 1:
                loaded = _load_callable_from_file(path, symbol, project_dir)
                if loaded.get("reason") and loaded.get("reason") != "target_not_callable":
                    isolated = load_source_isolated_callable(path, symbol)
                    if not isolated.get("reason"):
                        failure = import_failure(exc)
                        isolated["fallback_reason"] = failure["reason"]
                        isolated["fallback_detail"] = failure["detail"]
                        isolated["source_isolated"] = True
                        return isolated
                    failure = import_failure(exc)
                    loaded["reason"] = failure["reason"]
                    loaded["detail"] = failure["detail"]
                return loaded
            failure = import_failure(exc)
            return {"callable": None, "reason": failure["reason"], "detail": failure["detail"]}
    return _load_callable_from_file(path, symbol, project_dir)


def _has_unbounded_top_level_loop(path: Path) -> bool:
    try:
        tree, _ = parse_compatible_source(path.read_text(encoding="utf-8"), str(path))
    except (OSError, UnicodeError, SyntaxError):
        return False
    return any(
        isinstance(node, ast.While)
        and isinstance(node.test, ast.Constant)
        and node.test.value is True
        for node in tree.body
    )


def import_failure(exc: Exception) -> dict[str, str]:
    if isinstance(exc, ModuleNotFoundError):
        return {"reason": "import_failed_missing_module", "detail": _exception_detail(exc)}
    if isinstance(exc, ImportError):
        return {"reason": "import_failed_import_error", "detail": _exception_detail(exc)}
    return {"reason": "import_failed_runtime_error", "detail": _exception_detail(exc)}


def module_name_from_path(path_text: str) -> str:
    parts = Path(path_text).with_suffix("").parts
    if parts and parts[0] == "src":
        parts = parts[1:]
    if not parts:
        return ""
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


@contextmanager
def fresh_import(module_name: str):
    top = module_name.split(".", 1)[0]
    names = [name for name in list(sys.modules) if name == top or name.startswith(f"{top}.")]
    saved = {name: sys.modules.pop(name) for name in names}
    try:
        yield
    finally:
        for name in [name for name in list(sys.modules) if name == top or name.startswith(f"{top}.")]:
            sys.modules.pop(name, None)
        sys.modules.update(saved)


@contextmanager
def import_path(project_dir: Path):
    entries = [str(project_dir)]
    if (project_dir / "src").is_dir():
        entries.insert(0, str(project_dir / "src"))
    if (project_dir / "src" / "python").is_dir():
        entries.insert(0, str(project_dir / "src" / "python"))
    for entry in reversed(entries):
        sys.path.insert(0, entry)
    try:
        yield
    finally:
        for entry in entries:
            try:
                sys.path.remove(entry)
            except ValueError:
                pass


def _import_module_with_optional_stubs(project_dir: Path, module_name: str) -> dict[str, Any]:
    stubbed: list[str] = []
    created_modules: list[str] = []
    profile_modules: list[str] = []
    policy = dependency_stub_policy()
    created_modules.extend(_preinstall_profile_modules(project_dir, module_name, policy, profile_modules))
    attempts = max(1, int(policy.get("max_missing_modules") or 0) + 1)
    with _dependency_metadata_context(policy) as metadata_used:
        for _ in range(attempts):
            try:
                return _loaded_module(importlib.import_module(module_name), stubbed, created_modules, metadata_used, profile_modules)
            except ModuleNotFoundError as exc:
                missing = str(getattr(exc, "name", "") or "")
                if _can_profile_module(missing, policy, profile_modules):
                    created_modules.extend(_install_profile_module(missing, policy))
                    profile_modules.append(missing)
                    continue
                if not _can_stub_missing(project_dir, missing, policy, stubbed):
                    raise
                created_modules.extend(_install_stub_module(missing))
                stubbed.append(missing)
        return _loaded_module(importlib.import_module(module_name), stubbed, created_modules, metadata_used, profile_modules)


def _load_callable_from_file(path: Path, symbol: str, project_dir: Path, preprofiled: list[str] | None = None) -> dict[str, Any]:
    try:
        spec = importlib.util.spec_from_file_location("acceptance_probe_target", path)
        if not spec or not spec.loader:
            return {"callable": None, "reason": "import_failed"}
        module = importlib.util.module_from_spec(spec)
        stubbed: list[str] = []
        created_modules: list[str] = []
        profile_modules: list[str] = list(preprofiled or [])
        policy = dependency_stub_policy()
        attempts = max(1, int(policy.get("max_missing_modules") or 0) + 1)
        with _dependency_metadata_context(policy) as metadata_used:
            for _ in range(attempts):
                try:
                    spec.loader.exec_module(module)
                    break
                except ModuleNotFoundError as exc:
                    missing = str(getattr(exc, "name", "") or "")
                    if _can_profile_module(missing, policy, profile_modules):
                        created_modules.extend(_install_profile_module(missing, policy))
                        profile_modules.append(missing)
                        continue
                    if not _can_stub_missing(project_dir, missing, policy, stubbed):
                        raise
                    created_modules.extend(_install_stub_module(missing))
                    stubbed.append(missing)
        func = getattr(module, symbol, None)
        return {
            "callable": func,
            "module": module,
            "reason": "" if func is not None else "target_not_callable",
            "dependency_stubs": stubbed,
            "dependency_stub_modules_created": created_modules,
            "dependency_metadata_profiles": metadata_used,
            "dependency_module_profiles": profile_modules,
        }
    except (Exception, SystemExit) as exc:
        missing = str(getattr(exc, "name", "") or "")
        policy = dependency_stub_policy()
        if _can_profile_module(missing, policy, list(preprofiled or [])):
            _install_profile_module(missing, policy)
            return _load_callable_from_file(path, symbol, project_dir, [*(preprofiled or []), missing])
        failure = import_failure(exc)
        return {"callable": None, "reason": failure["reason"], "detail": failure["detail"]}


def _can_stub_missing(project_dir: Path, missing: str, policy: dict[str, Any], stubbed: list[str]) -> bool:
    if not policy.get("enabled") or not policy.get("stub_external_missing_modules") or not missing:
        return False
    if missing in stubbed or len(stubbed) >= int(policy.get("max_missing_modules") or 0):
        return False
    top = missing.split(".", 1)[0]
    return not (project_dir / top).exists() and not (project_dir / "src" / top).exists()


def _can_profile_module(missing: str, policy: dict[str, Any], profiled: list[str]) -> bool:
    if not policy.get("generated_module_profiles_enabled") or not missing or missing in profiled:
        return False
    profiles = dict(policy.get("generated_module_profiles") or {})
    return missing in profiles


def _preinstall_profile_modules(project_dir: Path, module_name: str, policy: dict[str, Any], profiled: list[str]) -> list[str]:
    if not policy.get("generated_module_profiles_enabled") or not module_name:
        return []
    created: list[str] = []
    top = module_name.split(".", 1)[0]
    for name in dict(policy.get("generated_module_profiles") or {}):
        if name in sys.modules or name in profiled or name.split(".", 1)[0] != top:
            continue
        if _profile_module_file_exists(project_dir, name):
            continue
        created.extend(_install_profile_module(name, policy))
        profiled.append(name)
    return created


def _profile_module_file_exists(project_dir: Path, name: str) -> bool:
    parts = name.split(".")
    relative = Path(*parts)
    candidates = [project_dir / relative.with_suffix(".py"), project_dir / "src" / relative.with_suffix(".py")]
    return any(path.exists() for path in candidates)


def _install_profile_module(name: str, policy: dict[str, Any]) -> list[str]:
    created: list[str] = []
    parts = name.split(".")
    for index in range(1, len(parts)):
        parent_name = ".".join(parts[:index])
        if parent_name not in sys.modules:
            parent = types.ModuleType(parent_name)
            parent.__path__ = []
            sys.modules[parent_name] = parent
            created.append(parent_name)
        if index > 1:
            setattr(sys.modules[".".join(parts[: index - 1])], parts[index - 1], sys.modules[parent_name])
    module = types.ModuleType(name)
    attrs = dict(dict(policy.get("generated_module_profiles") or {}).get(name, {}).get("attrs") or {})
    for key, value in attrs.items():
        setattr(module, str(key), _profile_attr_value(value))
    sys.modules[name] = module
    parent_name, _, child_name = name.rpartition(".")
    parent = sys.modules.get(parent_name)
    if parent is not None:
        setattr(parent, child_name, module)
    return [*created, name]


def _profile_attr_value(value: Any) -> Any:
    if isinstance(value, dict) and value.get("__fixture__") == "callable_empty_string":
        return lambda *args, **kwargs: ""
    return materialize(value)


def _is_stub_object(value: Any) -> bool:
    return value.__class__.__name__ == "_StubObject" and hasattr(value, "_name")


def _isolated_with_loaded(path: Path, symbol: str, loaded: dict[str, Any]) -> dict[str, Any] | None:
    isolated = load_source_isolated_callable(path, symbol)
    if isolated.get("reason"): return None
    isolated.update({key: loaded.get(key, []) for key in ("dependency_stubs", "dependency_stub_modules_created", "dependency_metadata_profiles", "dependency_module_profiles")})
    isolated["source_isolated"] = True; return isolated
def _remove_new_modules(before: set[str]) -> None:
    for name in [name for name in list(sys.modules) if name not in before]:
        sys.modules.pop(name, None)


def _loaded_module(
    module: Any,
    stubbed: list[str],
    created_modules: list[str],
    metadata_used: list[str],
    profile_modules: list[str],
) -> dict[str, Any]:
    return {
        "module": module,
        "dependency_stubs": stubbed,
        "dependency_stub_modules_created": created_modules,
        "dependency_metadata_profiles": metadata_used,
        "dependency_module_profiles": profile_modules,
    }


@contextmanager
def _dependency_metadata_context(policy: dict[str, Any]):
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

    def distribution(name: str) -> _StubDistribution:
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


def cleanup_dependency_stubs(loaded: dict[str, Any]) -> None:
    for name in reversed(list(loaded.get("dependency_stub_modules_created") or [])):
        sys.modules.pop(str(name), None)


def install_dependency_profile_modules(names: list[str]) -> list[str]:
    policy = dependency_stub_policy()
    return [created for name in names for created in _install_profile_module(str(name), policy)]


def _install_stub_module(name: str) -> list[str]:
    created: list[str] = []
    parts = name.split(".")
    for index in range(1, len(parts) + 1):
        module_name = ".".join(parts[:index])
        if module_name not in sys.modules:
            sys.modules[module_name] = _StubModule(module_name)
            created.append(module_name)
    return created


class _StubModule(types.ModuleType):
    def __init__(self, name: str):
        super().__init__(name)
        self.__path__, self.__all__ = [], []

    def __getattr__(self, name: str) -> Any:
        value = _StubObject(f"{self.__name__}.{name}")
        setattr(self, name, value)
        return value


class _StubObject:
    def __init__(self, name: str):
        self._name = name
    def __call__(self, *args: Any, **kwargs: Any) -> "_StubObject": return self
    def __getitem__(self, key: Any) -> "_StubObject": return _StubObject(f"{self._name}[{key!r}]")
    def __enter__(self) -> "_StubObject": return self
    def __exit__(self, *args: Any) -> bool: return False
    def __iter__(self): return iter(())
    def __bool__(self) -> bool: return False
    def __mro_entries__(self, bases: tuple[object, ...]) -> tuple[()]: return ()
    def __getattr__(self, name: str) -> "_StubObject": return _StubObject(f"{self._name}.{name}")

def _exception_detail(exc: Exception) -> str:
    name = getattr(exc, "name", "") or ""
    message = str(exc).splitlines()[0] if str(exc) else exc.__class__.__name__
    if name:
        return f"{name}: {message}"[:240]
    return message[:240]
