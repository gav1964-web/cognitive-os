"""Load interface contracts used by sandbox programmer packages."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_interface_contracts(root: Path) -> dict[str, dict[str, Any]]:
    path = root / "registry" / "interface_contracts.json"
    if not path.is_file():
        path = Path(__file__).resolve().parents[1] / "registry" / "interface_contracts.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "interface_contracts.v1":
        raise ValueError("unsupported interface contracts schema")
    rows = payload.get("contracts")
    if not isinstance(rows, list):
        raise ValueError("interface_contracts.json requires contracts list")
    contracts = {}
    for row in rows:
        item = dict(row)
        contract_id = str(item.get("id") or "")
        if not contract_id:
            raise ValueError("interface contract requires id")
        contracts[contract_id] = item
    return contracts


def interface_contract_for_operation(root: Path, operation: dict[str, Any]) -> dict[str, Any]:
    profile = str(operation.get("profile") or "")
    if profile == "numeric_args_file_expression":
        contract_id = "argv_to_file_numeric_expression"
    elif profile.startswith("numeric_args_"):
        contract_id = "argv_stdout_numeric_expression"
    elif profile == "stdin_file_text_expression":
        contract_id = "stdin_to_file_text_transform"
    elif profile == "stdin_text_expression":
        contract_id = "stdin_to_stdout_text_transform"
    elif profile == "file_stdout_text_expression":
        contract_id = "file_to_stdout_text_transform"
    else:
        contract_id = "file_to_file_text_transform"
    contracts = load_interface_contracts(root)
    contract = dict(contracts[contract_id])
    contract["selected_for_operation"] = operation.get("operation")
    return contract
