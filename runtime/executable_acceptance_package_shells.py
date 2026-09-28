"""Temporary namespace package shells for source-isolated imports."""

from __future__ import annotations

import sys
import types
from contextlib import contextmanager
from pathlib import Path
from typing import Any


@contextmanager
def fresh_local_package(namespace: dict[str, Any], path: Path):
    package = str(namespace.get("__package__") or "")
    top = package.split(".", 1)[0]
    names = [name for name in list(sys.modules) if top and (name == top or name.startswith(f"{top}."))]
    saved = {name: sys.modules.pop(name) for name in names}
    _install_package_shells(package, path)
    try:
        yield
    finally:
        for name in [name for name in list(sys.modules) if top and (name == top or name.startswith(f"{top}."))]:
            sys.modules.pop(name, None)
        sys.modules.update(saved)


def _install_package_shells(package: str, path: Path) -> None:
    if not package:
        return
    parts = package.split(".")
    directories: list[Path] = []
    current = path.resolve().parent
    for _ in reversed(parts):
        directories.append(current)
        current = current.parent
    for index, directory in enumerate(reversed(directories), start=1):
        name = ".".join(parts[:index])
        module = types.ModuleType(name)
        module.__package__, module.__path__ = name, [str(directory)]
        sys.modules[name] = module
        if index > 1:
            setattr(sys.modules[".".join(parts[: index - 1])], parts[index - 1], module)
