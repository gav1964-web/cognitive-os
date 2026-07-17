from __future__ import annotations

import json

import pytest

from runtime.contract_registry import ContractRegistryError, load_artifact_contracts


def test_artifact_contracts_are_loaded_from_external_config():
    contracts = load_artifact_contracts()

    assert "TechnicalSpec" in contracts
    assert "required_fields" in contracts["TechnicalSpec"]
    assert "producer" in contracts["TechnicalSpec"]


def test_artifact_contract_loader_rejects_bad_schema(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"schema_version": "wrong", "contracts": {}}), encoding="utf-8")

    with pytest.raises(ContractRegistryError):
        load_artifact_contracts(str(path))
