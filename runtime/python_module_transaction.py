"""Process-local import isolation for sequential project analysis."""

from __future__ import annotations

import sys
from contextlib import contextmanager
from types import ModuleType
from typing import Iterator


@contextmanager
def python_module_transaction() -> Iterator[None]:
    """Restore ``sys.modules`` after probing untrusted project imports."""
    before: dict[str, ModuleType] = dict(sys.modules)
    try:
        yield
    finally:
        for name in tuple(sys.modules):
            if name not in before:
                sys.modules.pop(name, None)
        for name, module in before.items():
            if sys.modules.get(name) is not module:
                sys.modules[name] = module
