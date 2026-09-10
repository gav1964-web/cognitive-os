"""Callable loading helpers for executable acceptance harness analysis."""

from __future__ import annotations

import ast
import importlib
import importlib.util
import sys
import types
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .executable_acceptance_dependency_profiles import (
    can_profile_module as _can_profile_module,
    dependency_metadata_context as _dependency_metadata_context,
    discard_synthetic_local_parent as _discard_synthetic_local_parent,
    install_dependency_profile_modules,
    install_profile_module as _install_profile_module,
    preinstall_profile_modules as _preinstall_profile_modules,
)
from .executable_acceptance_isolation import load_source_isolated_callable
from .executable_acceptance_module_path import module_name_from_path, package_import_root
from .executable_acceptance_policy import dependency_stub_policy
from .executable_acceptance_stub_budget import can_stub_missing as _can_stub_missing
from .executable_acceptance_stub_budget import stub_attempt_budget
from .python_parser_compatibility import parse_compatible_source

def load_supported_callable(project_dir: Path, path_text: str, symbol: str, path: Path) -> dict[str, Any]:
    if _has_unbounded_top_level_loop(path):
        isolated = load_source_isolated_callable(path, symbol)
        if not isolated.get("reason"):
            isolated["source_isolated"] = True
            return isolated
    module_name = module_name_from_path(path_text, path)
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
            _remove_new_modules(locals().get("before_modules", set()), project_dir)
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
def import_path(project_dir: Path, target_path: Path | None = None):
    entries = [str(project_dir)]
    if (project_dir / "src").is_dir():
        entries.insert(0, str(project_dir / "src"))
    if (project_dir / "src" / "python").is_dir():
        entries.insert(0, str(project_dir / "src" / "python"))
    target_root = package_import_root(target_path)
    if target_root and str(target_root) not in entries:
        entries.insert(0, str(target_root))
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
    attempts = stub_attempt_budget(policy)
    try:
        with _dependency_metadata_context(policy) as metadata_used:
            for _ in range(attempts):
                try:
                    return _loaded_module(importlib.import_module(module_name), stubbed, created_modules, metadata_used, profile_modules)
                except ModuleNotFoundError as exc:
                    missing = str(getattr(exc, "name", "") or "")
                    if _can_profile_module(missing, policy, profile_modules):
                        created = _install_profile_module(missing, policy)
                        _discard_synthetic_local_parent(project_dir, missing, created)
                        created_modules.extend(created)
                        profile_modules.append(missing)
                        continue
                    if not _can_stub_missing(project_dir, missing, policy, stubbed):
                        raise
                    created_modules.extend(_install_stub_module(missing))
                    stubbed.append(missing)
                    _clear_import_tree(module_name)
            return _loaded_module(importlib.import_module(module_name), stubbed, created_modules, metadata_used, profile_modules)
    except BaseException:
        for name in reversed(created_modules):
            sys.modules.pop(name, None)
        raise


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
        attempts = stub_attempt_budget(policy)
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


def _clear_import_tree(module_name: str) -> None:
    top = module_name.split(".", 1)[0]
    for name in [key for key in list(sys.modules) if key == top or key.startswith(f"{top}.")]:
        sys.modules.pop(name, None)


def _is_stub_object(value: Any) -> bool:
    return value.__class__.__name__ == "_StubObject" and hasattr(value, "_name")


def _isolated_with_loaded(path: Path, symbol: str, loaded: dict[str, Any]) -> dict[str, Any] | None:
    isolated = load_source_isolated_callable(path, symbol)
    if isolated.get("reason"): return None
    isolated.update({key: loaded.get(key, []) for key in ("dependency_stubs", "dependency_stub_modules_created", "dependency_metadata_profiles", "dependency_module_profiles")})
    isolated["source_isolated"] = True; return isolated
def _remove_new_modules(before: set[str], project_dir: Path) -> None:
    project_root = project_dir.resolve()
    for name in [name for name in list(sys.modules) if name not in before]:
        module_file = str(getattr(sys.modules.get(name), "__file__", "") or "")
        if not module_file:
            continue
        try:
            owned = Path(module_file).resolve().is_relative_to(project_root)
        except (OSError, ValueError):
            owned = False
        if owned:
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

def cleanup_dependency_stubs(loaded: dict[str, Any]) -> None:
    for name in reversed(list(loaded.get("dependency_stub_modules_created") or [])):
        sys.modules.pop(str(name), None)


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
        self.__file__ = f"<dependency-stub:{name}>"
        self.__spec__ = importlib.util.spec_from_loader(name, loader=None, is_package=True)

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
