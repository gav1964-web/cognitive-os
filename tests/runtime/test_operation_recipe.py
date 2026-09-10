from __future__ import annotations

from runtime.operation_recipe import recipe_from_operation, validate_operation_recipe


def test_operation_recipe_from_numeric_operation():
    recipe = recipe_from_operation(
        {
            "operation": "demo",
            "profile": "numeric_args_expression",
            "expression": "a+b",
            "evidence": ["expression:a+b"],
        },
        interface_contract={
            "id": "argv_stdout_numeric_expression",
            "input": {"shape": "numeric_args"},
            "output": {"shape": "text_number"},
        },
    )

    assert recipe["artifact_type"] == "OperationRecipe"
    assert recipe["status"] == "ready"
    assert recipe["interface_contract"] == "argv_stdout_numeric_expression"
    assert recipe["transform"] == "numeric_expression"
    assert recipe["expression"] == "a+b"
    assert validate_operation_recipe(recipe) == (True, [])


def test_operation_recipe_validation_rejects_unknown_transform():
    ok, errors = validate_operation_recipe(
        {
            "artifact_type": "OperationRecipe",
            "status": "ready",
            "interface_contract": "stdin_to_stdout_text_transform",
            "transform": "run_shell",
            "expression": None,
        }
    )

    assert ok is False
    assert "unsupported_transform" in errors


def test_operation_recipe_validation_accepts_output_file_contracts():
    for contract, transform, expression in [
        ("stdin_to_file_text_transform", "uppercase", None),
        ("argv_to_file_numeric_expression", "numeric_expression", "a+b"),
    ]:
        ok, errors = validate_operation_recipe(
            {
                "artifact_type": "OperationRecipe",
                "status": "ready",
                "interface_contract": contract,
                "transform": transform,
                "expression": expression,
            }
        )

        assert ok is True
        assert errors == []
