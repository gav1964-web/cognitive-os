from __future__ import annotations

from pathlib import Path

from runtime.interface_contracts import interface_contract_for_operation, load_interface_contracts


ROOT = Path(__file__).resolve().parents[2]


def test_interface_contract_registry_loads_core_contracts():
    contracts = load_interface_contracts(ROOT)

    assert set(contracts) >= {
        "argv_stdout_numeric_expression",
        "file_to_file_text_transform",
        "stdin_to_stdout_text_transform",
        "file_to_stdout_text_transform",
        "stdin_to_file_text_transform",
        "argv_to_file_numeric_expression",
    }
    assert contracts["argv_stdout_numeric_expression"]["input"]["channel"] == "argv"
    assert contracts["argv_stdout_numeric_expression"]["output"]["channel"] == "stdout"
    assert contracts["file_to_file_text_transform"]["input"]["channel"] == "file"
    assert contracts["file_to_file_text_transform"]["output"]["channel"] == "file"
    assert contracts["stdin_to_stdout_text_transform"]["input"]["channel"] == "stdin"
    assert contracts["stdin_to_stdout_text_transform"]["output"]["channel"] == "stdout"
    assert contracts["file_to_stdout_text_transform"]["input"]["channel"] == "file"
    assert contracts["file_to_stdout_text_transform"]["output"]["channel"] == "stdout"
    assert contracts["stdin_to_file_text_transform"]["input"]["channel"] == "stdin"
    assert contracts["stdin_to_file_text_transform"]["output"]["channel"] == "file"
    assert contracts["argv_to_file_numeric_expression"]["input"]["channel"] == "argv"
    assert contracts["argv_to_file_numeric_expression"]["output"]["channel"] == "file"


def test_interface_contract_selected_from_operation_profile():
    numeric = interface_contract_for_operation(ROOT, {"operation": "demo", "profile": "numeric_args_expression"})
    text_file = interface_contract_for_operation(ROOT, {"operation": "demo", "profile": "text_expression"})
    stdin = interface_contract_for_operation(ROOT, {"operation": "demo", "profile": "stdin_text_expression"})
    stdin_file = interface_contract_for_operation(ROOT, {"operation": "demo", "profile": "stdin_file_text_expression"})
    file_stdout = interface_contract_for_operation(ROOT, {"operation": "demo", "profile": "file_stdout_text_expression"})
    numeric_file = interface_contract_for_operation(ROOT, {"operation": "demo", "profile": "numeric_args_file_expression"})

    assert numeric["id"] == "argv_stdout_numeric_expression"
    assert numeric["selected_for_operation"] == "demo"
    assert text_file["id"] == "file_to_file_text_transform"
    assert stdin["id"] == "stdin_to_stdout_text_transform"
    assert stdin_file["id"] == "stdin_to_file_text_transform"
    assert file_stdout["id"] == "file_to_stdout_text_transform"
    assert numeric_file["id"] == "argv_to_file_numeric_expression"
