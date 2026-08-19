"""Ephemeral filesystem fixtures for executable acceptance."""

from __future__ import annotations

import os
import tempfile
import pprint
from pathlib import Path


class _ReadableTempPath(os.PathLike[str]):
    def __init__(self) -> None:
        handle = tempfile.NamedTemporaryFile(prefix="cognitive-os-", suffix=".tmp", delete=False)
        handle.write(b"sample")
        handle.close()
        self.path = Path(handle.name)

    def __fspath__(self) -> str:
        return str(self.path)

    def __str__(self) -> str:
        return str(self.path)

    def __del__(self) -> None:
        self.path.unlink(missing_ok=True)


def readable_temp_path() -> os.PathLike[str]:
    return _ReadableTempPath()


class _PythonModulePath(_ReadableTempPath):
    def __init__(self, fields: dict[str, object]) -> None:
        handle = tempfile.NamedTemporaryFile(
            prefix="cognitive-os-module-", suffix=".py", delete=False, mode="w", encoding="utf-8"
        )
        for name, value in sorted(fields.items()):
            if name.isidentifier():
                handle.write(f"{name} = {pprint.pformat(value)}\n")
        handle.close()
        self.path = Path(handle.name)


def python_module_path(fields: dict[str, object]) -> os.PathLike[str]:
    return _PythonModulePath(fields)
