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


class _TemporaryDirectoryPath(os.PathLike[str]):
    def __init__(self) -> None:
        self.directory = tempfile.TemporaryDirectory(prefix="cognitive-os-directory-")
        self.path = Path(self.directory.name)

    def __fspath__(self) -> str:
        return str(self.path)

    def __str__(self) -> str:
        return str(self.path)


def temporary_directory() -> os.PathLike[str]:
    return _TemporaryDirectoryPath()


def delimited_text_path(delimiter: str, columns: int) -> os.PathLike[str]:
    handle = tempfile.NamedTemporaryFile(
        prefix="cognitive-os-delimited-", suffix=".txt", delete=False, mode="w", encoding="utf-8"
    )
    handle.write(delimiter.join("sample" for _ in range(max(1, columns))) + "\n")
    handle.close()
    result = object.__new__(_ReadableTempPath)
    result.path = Path(handle.name)
    return result


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
