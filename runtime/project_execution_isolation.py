"""Keep sequential project probes from sharing imported project state."""

from __future__ import annotations

import contextlib
import sys
from collections.abc import Iterator
from types import ModuleType


@contextlib.contextmanager
def isolated_project_execution() -> Iterator[None]:
    modules_before: dict[str, ModuleType] = dict(sys.modules)
    path_before = list(sys.path)
    argv_before = list(sys.argv)
    try:
        yield
    finally:
        for name in set(sys.modules).difference(modules_before):
            sys.modules.pop(name, None)
        for name, module in modules_before.items():
            if sys.modules.get(name) is not module:
                sys.modules[name] = module
        sys.path[:] = path_before
        sys.argv[:] = argv_before
