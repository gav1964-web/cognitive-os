"""Load deterministic project change recipes from external configuration."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = ROOT / "config" / "project_change_recipes.json"


class ProjectChangeRecipeError(RuntimeError):
    """Raised when project change recipes are invalid."""


@lru_cache(maxsize=1)
def load_project_change_recipes(path: str | None = None) -> dict[str, Any]:
    source = Path(path) if path else RULES_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "project_change_recipes.v1":
        raise ProjectChangeRecipeError("project change recipes must use schema_version project_change_recipes.v1")
    if payload.get("status") != "active":
        raise ProjectChangeRecipeError("project change recipes must be active")
    recipes = payload.get("recipes")
    if not isinstance(recipes, dict) or not recipes:
        raise ProjectChangeRecipeError("project change recipes require non-empty recipes object")
    for recipe_id, recipe in recipes.items():
        if not isinstance(recipe, dict) or not isinstance(recipe.get("files"), dict):
            raise ProjectChangeRecipeError(f"recipe requires files object: {recipe_id}")
    return payload


def get_project_change_recipe(recipe_id: str, *, rules: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = rules or load_project_change_recipes()
    recipe = dict(payload.get("recipes") or {}).get(recipe_id)
    if not isinstance(recipe, dict):
        raise ProjectChangeRecipeError(f"unknown project change recipe: {recipe_id}")
    return recipe
