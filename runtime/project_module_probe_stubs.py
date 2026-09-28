"""Controlled dependency stubs for module import probes."""

from __future__ import annotations

import importlib
import importlib.metadata
import sys
import types
from pathlib import Path
from typing import Any

from .executable_acceptance_policy import dependency_stub_policy


PROBE_VERSION = "0.0.0"


def import_with_dependency_stubs(project_root: Path, module_name: str) -> dict[str, Any]:
    policy = dependency_stub_policy()
    stubbed: list[str] = []
    max_missing = int(policy.get("max_missing_modules") or 0)
    while True:
        try:
            return {"module": importlib.import_module(module_name), "dependency_stubs": stubbed}
        except ModuleNotFoundError as exc:
            missing = str(getattr(exc, "name", "") or "")
            if missing in {f"{module_name.split('.', 1)[0]}._version", f"{module_name.split('.', 1)[0]}.version"}:
                install_version_fallbacks(module_name)
                continue
            if not _can_stub_missing(project_root, missing, policy, stubbed, max_missing):
                raise
            _remove_project_modules(module_name)
            install_version_fallbacks(module_name)
            _install_stub_module(missing)
            stubbed.append(missing)
        except Exception as exc:
            retry = _plugin_loader_retry_module(project_root, policy, stubbed, exc)
            if not retry:
                setattr(exc, "dependency_stubs", list(stubbed))
                raise
            _remove_project_modules(module_name)
            _remove_named_modules([retry])
            install_version_fallbacks(module_name)
            _install_stub_module(retry)
            stubbed.append(retry)


def install_version_fallbacks(module_name: str) -> None:
    root = module_name.split(".", 1)[0]
    private_version = types.ModuleType(f"{root}._version")
    private_version.__version__ = PROBE_VERSION
    private_version.version = PROBE_VERSION
    sys.modules.setdefault(f"{root}._version", private_version)
    public_version = types.ModuleType(f"{root}.version")
    public_version.version = PROBE_VERSION
    public_version.version_tuple = (0, 0, 0, "probe")
    public_version.__version__ = PROBE_VERSION
    sys.modules.setdefault(f"{root}.version", public_version)
    original_version = importlib.metadata.version
    original_metadata = importlib.metadata.metadata
    original_distribution = importlib.metadata.distribution

    def version(name: str) -> str:
        try:
            return original_version(name)
        except importlib.metadata.PackageNotFoundError:
            if name.replace("-", "_") == root.replace("-", "_"):
                return PROBE_VERSION
            raise

    def metadata(name: str) -> Any:
        try:
            return original_metadata(name)
        except importlib.metadata.PackageNotFoundError:
            if name.replace("-", "_") == root.replace("-", "_"):
                return _ProbeMetadata(str(name))
            raise

    def distribution(name: str) -> Any:
        try:
            return original_distribution(name)
        except importlib.metadata.PackageNotFoundError:
            if name.replace("-", "_") == root.replace("-", "_"):
                return _ProbeDistribution(str(name))
            raise

    importlib.metadata.version = version
    importlib.metadata.metadata = metadata
    importlib.metadata.distribution = distribution


def _plugin_loader_retry_module(project_root: Path, policy: dict[str, Any], stubbed: list[str], exc: Exception) -> str:
    reason = f"{type(exc).__name__}: {exc}".lower()
    if "extensionmanager" not in reason and "object is not iterable" not in reason:
        return ""
    for name in policy.get("pre_stub_modules", []):
        module = str(name)
        if _can_stub_missing(project_root, module, {**policy, "stub_external_missing_modules": True}, stubbed, 100):
            return module
    return ""


def _remove_named_modules(names: list[str]) -> None:
    roots = {name.split(".", 1)[0] for name in names}
    for name in [name for name in list(sys.modules) if name.split(".", 1)[0] in roots]:
        sys.modules.pop(name, None)


def _remove_project_modules(module_name: str) -> None:
    root = module_name.split(".", 1)[0]
    for name in [name for name in list(sys.modules) if name == root or name.startswith(f"{root}.")]:
        sys.modules.pop(name, None)


def _can_stub_missing(project_root: Path, missing: str, policy: dict[str, Any], stubbed: list[str], max_missing: int) -> bool:
    if not policy.get("enabled") or not policy.get("stub_external_missing_modules") or not missing:
        return False
    top = missing.split(".", 1)[0]
    stubbed_roots = {name.split(".", 1)[0] for name in stubbed}
    if missing in stubbed or (top not in stubbed_roots and len(stubbed_roots) >= max_missing):
        return False
    return not (project_root / top).exists() and not (project_root / "src" / top).exists()


def _install_stub_module(name: str) -> None:
    parts = name.split(".")
    for index in range(1, len(parts) + 1):
        module_name = ".".join(parts[:index])
        if module_name not in sys.modules:
            sys.modules[module_name] = _StubModule(module_name)


class _StubModule(types.ModuleType):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.__path__ = []
        self.__version__ = PROBE_VERSION

    def __getattr__(self, name: str) -> Any:
        if name[:1].isupper():
            value = _stub_class(name)
        else:
            value = _StubObject(f"{self.__name__}.{name}")
        setattr(self, name, value)
        return value


class _StubObject:
    def __init__(self, name: str) -> None:
        self._name = name

    def __call__(self, *args: Any, **kwargs: Any) -> "_StubObject":
        return self

    def __getitem__(self, key: Any) -> "_StubObject":
        return _StubObject(f"{self._name}[{key!r}]")

    def __add__(self, other: Any) -> "_StubObject":
        return self

    def __radd__(self, other: Any) -> Any:
        return f"{other}{self}" if isinstance(other, str) else self

    def __iadd__(self, other: Any) -> "_StubObject":
        return self

    def __enter__(self) -> "_StubObject":
        return self

    def __exit__(self, *args: Any) -> bool:
        return False

    def __iter__(self):
        return iter(())

    def __bool__(self) -> bool:
        return False

    def __fspath__(self) -> str:
        return "."

    def __str__(self) -> str:
        return "stub"

    def __lt__(self, other: Any) -> bool:
        return False

    def __le__(self, other: Any) -> bool:
        return False

    def __gt__(self, other: Any) -> bool:
        return False

    def __ge__(self, other: Any) -> bool:
        return False

    def __mro_entries__(self, bases: tuple[object, ...]) -> tuple[()] :
        return ()

    def __getattr__(self, name: str) -> "_StubObject":
        if name[:1].isupper():
            return _stub_class(name)
        return _StubObject(f"{self._name}.{name}")


def _stub_class(name: str) -> type:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._name = name
        self._stub_name = name

    return type(name, (_StubObject,), {"__init__": __init__, "__class_getitem__": classmethod(lambda cls, item: cls)})


class _ProbeDistribution:
    def __init__(self, name: str) -> None:
        self.metadata = _ProbeMetadata(name)

    @property
    def version(self) -> str:
        return PROBE_VERSION


class _ProbeMetadata(dict):
    def __init__(self, name: str) -> None:
        super().__init__(
            {
                "Name": name,
                "Author": "Probe Author",
                "Project-URL": f"Homepage, https://example.invalid/{name}",
                "Summary": f"{name} probe package",
                "Version": PROBE_VERSION,
                "author-email": "Probe Author <probe@example.invalid>",
                "author": "Probe Author",
                "name": name,
                "project-url": f"Homepage, https://example.invalid/{name}",
                "summary": f"{name} probe package",
                "version": PROBE_VERSION,
            }
        )

    def __getitem__(self, key: str) -> str:
        if key in self:
            return super().__getitem__(key)
        lowered = key.lower()
        if lowered in self:
            return super().__getitem__(lowered)
        titled = key[:1].upper() + key[1:].lower()
        return super().__getitem__(titled)

    def get_all(self, key: str, default: Any = None) -> list[str] | Any:
        try:
            return [self[key]]
        except KeyError:
            return default
