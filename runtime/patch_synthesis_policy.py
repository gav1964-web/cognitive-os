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


def missing_registry_env_fallback_recipe() -> dict[str, Any]:
    recipes = dict(_policy().get("recipes") or {})
    recipe = dict(recipes.get("missing_registry_env_fallback") or {})
    return recipe if recipe.get("enabled", True) else {}


def timestamp_range_error_contract_recipe() -> dict[str, Any]:
    recipes = dict(_policy().get("recipes") or {})
    recipe = dict(recipes.get("timestamp_range_error_contract") or {})
    return recipe if recipe.get("enabled", True) else {}


def falsy_primitive_empty_contract_recipe() -> dict[str, Any]:
    recipes = dict(_policy().get("recipes") or {})
    recipe = dict(recipes.get("falsy_primitive_empty_contract") or {})
    return recipe if recipe.get("enabled", True) else {}


def incomplete_import_token_contract_recipe() -> dict[str, Any]:
    recipes = dict(_policy().get("recipes") or {})
    recipe = dict(recipes.get("incomplete_import_token_contract") or {})
    return recipe if recipe.get("enabled", True) else {}


def duplicate_cli_short_option_contract_recipe() -> dict[str, Any]:
    recipes = dict(_policy().get("recipes") or {})
    recipe = dict(recipes.get("duplicate_cli_short_option_contract") or {})
    return recipe if recipe.get("enabled", True) else {}


def strict_default_string_comparison_contract_recipe() -> dict[str, Any]:
    recipes = dict(_policy().get("recipes") or {})
    recipe = dict(recipes.get("strict_default_string_comparison_contract") or {})
    return recipe if recipe.get("enabled", True) else {}


def escaped_fstring_brace_offset_contract_recipe() -> dict[str, Any]:
    recipes = dict(_policy().get("recipes") or {})
    recipe = dict(recipes.get("escaped_fstring_brace_offset_contract") or {})
    return recipe if recipe.get("enabled", True) else {}


def trailing_backslash_bounds_contract_recipe() -> dict[str, Any]:
    recipes = dict(_policy().get("recipes") or {})
    recipe = dict(recipes.get("trailing_backslash_index_contract") or {})
    return recipe if recipe.get("enabled", True) else {}


def cli_help_type_placeholder_contract_recipe() -> dict[str, Any]:
    recipes = dict(_policy().get("recipes") or {})
    recipe = dict(recipes.get("cli_help_type_placeholder_contract") or {})
    return recipe if recipe.get("enabled", True) else {}


def framework_contract_recipe(operation_kind: str) -> dict[str, Any]:
    recipes = dict(_policy().get("recipes") or {})
    recipe = dict(recipes.get(operation_kind) or {})
    return recipe if recipe.get("enabled", True) else {}


def training_repair_recipe(operation_kind: str) -> dict[str, Any]:
    recipes = dict(_policy().get("recipes") or {})
    recipe = dict(recipes.get(operation_kind) or {})
    if recipe.get("authority") != "training_only":
        return {}
    return recipe if recipe.get("enabled", True) else {}


def return_literal_stub_recipe() -> dict[str, Any]:
    recipes = dict(_policy().get("recipes") or {})
    recipe = dict(recipes.get("return_literal_stub") or {})
    return recipe if recipe.get("enabled", True) else {}


def return_literal_notimplemented_recipe() -> dict[str, Any]:
    recipes = dict(_policy().get("recipes") or {})
    recipe = dict(recipes.get("return_literal_notimplemented") or {})
    return recipe if recipe.get("enabled", True) else {}


def string_transform_identity_return_recipe() -> dict[str, Any]:
    recipes = dict(_policy().get("recipes") or {})
    recipe = dict(recipes.get("contract_transform_identity_return") or recipes.get("string_transform_identity_return") or {})
    return recipe if recipe.get("enabled", True) else {}


def append_mapping_helper_recipe() -> dict[str, Any]:
    recipes = dict(_policy().get("recipes") or {})
    recipe = dict(recipes.get("extract_append_mapping_helper") or {})
    return recipe if recipe.get("enabled", True) else {}


def json_dumps_helper_recipe() -> dict[str, Any]:
    recipes = dict(_policy().get("recipes") or {})
    recipe = dict(recipes.get("extract_json_dumps_helper") or {})
    return recipe if recipe.get("enabled", True) else {}


def json_loads_helper_recipe() -> dict[str, Any]:
    recipes = dict(_policy().get("recipes") or {})
    recipe = dict(recipes.get("extract_json_loads_helper") or {})
    return recipe if recipe.get("enabled", True) else {}


def splitlines_helper_recipe() -> dict[str, Any]:
    recipes = dict(_policy().get("recipes") or {})
    recipe = dict(recipes.get("extract_splitlines_helper") or {})
    return recipe if recipe.get("enabled", True) else {}


def development_helper_extraction_recipe(operation_kind: str) -> dict[str, Any]:
    recipes = (
        append_mapping_helper_recipe(),
        json_dumps_helper_recipe(),
        json_loads_helper_recipe(),
        splitlines_helper_recipe(),
    )
    return next(
        (recipe for recipe in recipes if recipe.get("operation_kind") == operation_kind),
        {},
    )
