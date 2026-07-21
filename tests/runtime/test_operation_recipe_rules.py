from __future__ import annotations

from pathlib import Path

import pytest

from runtime.operation_recipe_rules import (
    OperationRecipeRulesError,
    allowed_interface_contracts,
    allowed_transforms,
    load_operation_recipe_rules,
)


ROOT = Path(__file__).resolve().parents[2]


def test_operation_recipe_rules_load_contracts_transforms_and_profiles():
    rules = load_operation_recipe_rules(str(ROOT / "config" / "operation_recipe_rules.json"))

    assert "stdin_to_file_text_transform" in allowed_interface_contracts(rules=rules)
    assert "word_count" in allowed_transforms(rules=rules)
    assert rules["contract_profiles"]["argv_to_file_numeric_expression"] == "numeric_args_file_expression"
    assert rules["text_transforms"]["uppercase"]["expression"] == "text.upper()"


def test_operation_recipe_rules_reject_unknown_contract_profile(tmp_path: Path):
    path = tmp_path / "rules.json"
    path.write_text(
        """{
  "schema_version": "operation_recipe_rules.v1",
  "status": "active",
  "allowed_interface_contracts": ["stdin_to_stdout_text_transform"],
  "allowed_transforms": ["numeric_expression", "uppercase"],
  "numeric": {},
  "text_transforms": {"uppercase": {"expression": "text.upper()", "markers": ["upper"]}},
  "contract_profiles": {"missing_contract": "stdin_text_expression"},
  "text_interface_markers": {},
  "text_interface_resolution": [],
  "l45_prompt": {}
}
""",
        encoding="utf-8",
    )

    with pytest.raises(OperationRecipeRulesError, match="unsupported contract"):
        load_operation_recipe_rules(str(path))
