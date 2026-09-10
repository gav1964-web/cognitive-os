"""Keep configured effect stubs active while an isolated callable runs."""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable
from typing import Any

from .executable_acceptance_effect_stubs import configured_effect_stubs


def with_runtime_effect_stubs(func: Callable[..., Any], modules: set[str]) -> Callable[..., Any]:
    if not modules:
        return func
    if inspect.iscoroutinefunction(func):
        @functools.wraps(func)
        async def async_call(*args: Any, **kwargs: Any) -> Any:
            with configured_effect_stubs(modules):
                return await func(*args, **kwargs)

        return async_call

    @functools.wraps(func)
    def call(*args: Any, **kwargs: Any) -> Any:
        with configured_effect_stubs(modules):
            return func(*args, **kwargs)

    return call
