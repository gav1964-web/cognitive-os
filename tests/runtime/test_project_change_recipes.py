from __future__ import annotations

from pathlib import Path

import pytest

from runtime.project_change_recipes import ProjectChangeRecipeError, get_project_change_recipe, load_project_change_recipes


ROOT = Path(__file__).resolve().parents[2]


def test_project_change_recipes_load_gigachat_recipe():
    rules = load_project_change_recipes(str(ROOT / "config" / "project_change_recipes.json"))
    recipe = get_project_change_recipe("disable_gigachat_auto_model", rules=rules)

    assert "app/gigachat/orchestrator.py" in recipe["files"]
    assert "classifier auto-selection" in recipe["contract"]


def test_project_change_recipes_reject_unknown_recipe():
    with pytest.raises(ProjectChangeRecipeError, match="unknown"):
        get_project_change_recipe("missing_recipe")
