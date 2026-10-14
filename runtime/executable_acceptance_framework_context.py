"""Apply config-declared framework contexts to isolated callables."""

from __future__ import annotations

import functools
import importlib
import inspect
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .executable_acceptance_policy import source_isolation_policy


def preload_framework_modules(imported_modules: set[str]) -> None:
    recipes = dict(source_isolation_policy().get("framework_contexts") or {})
    for recipe in recipes.values():
        module_name = str(recipe.get("factory_module") or "")
        if not module_name or not any(
            name == module_name or name.startswith(f"{module_name}.")
            for name in imported_modules
        ):
            continue
        try:
            importlib.import_module(module_name)
        except ImportError:
            continue


def with_framework_context(func: Callable[..., Any], path: Path) -> Callable[..., Any]:
    recipe = _matching_recipe(func)
    if not recipe:
        return func

    def context():
        module = importlib.import_module(str(recipe["factory_module"]))
        factory = getattr(module, str(recipe["factory_name"]))
        kwargs: dict[str, Any] = {}
        if recipe.get("source_root") == "parent":
            kwargs["root_path"] = str(path.resolve().parent)
        if recipe.get("template_folder"):
            kwargs["template_folder"] = str(recipe["template_folder"])
        application = factory("acceptance_probe", **kwargs)
        return getattr(application, str(recipe["context_method"]))()

    if inspect.iscoroutinefunction(func):
        @functools.wraps(func)
        async def async_call(*args: Any, **kwargs: Any) -> Any:
            with context():
                return await func(*args, **kwargs)

        return async_call

    @functools.wraps(func)
    def call(*args: Any, **kwargs: Any) -> Any:
        with context():
            return func(*args, **kwargs)

    return call


def _matching_recipe(func: Callable[..., Any]) -> dict[str, Any]:
    globals_map = getattr(func, "__globals__", {})
    modules = {
        str(getattr(value, "__module__", ""))
        for value in globals_map.values()
        if callable(value)
    }
    recipes = dict(source_isolation_policy().get("framework_contexts") or {})
    for recipe in recipes.values():
        prefixes = tuple(str(item) for item in recipe.get("trigger_modules", []) if item)
        if prefixes and any(module.startswith(prefixes) for module in modules):
            return dict(recipe)
    return {}
