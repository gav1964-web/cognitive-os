"""Config-backed policy for deterministic patch synthesis recipes."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "config" / "patch_synthesis_policy.json"


def load_patch_synthesis_policy(path: str | Path | None = None) -> dict[str, Any]:
    source = Path(path or DEFAULT_PATH)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "patch_synthesis_policy.v1":
        raise ValueError("Unsupported patch synthesis policy schema")
    return payload


@lru_cache(maxsize=1)
def _policy() -> dict[str, Any]:
    return load_patch_synthesis_policy()


def required_input_guard_recipe() -> dict[str, Any]:
    recipes = dict(_policy().get("recipes") or {})
    recipe = dict(recipes.get("required_input_guard") or {})
    return recipe if recipe.get("enabled", True) else {}
