from __future__ import annotations

import json
from pathlib import Path

import pytest

from runtime.contract_transform_operators import load_contract_transform_operators, operator_records


ROOT = Path(__file__).resolve().parents[2]


def test_contract_transform_operator_catalog_loads_allowed_records():
    catalog = load_contract_transform_operators(ROOT / "config" / "contract_transform_operators.json")
    records = operator_records({"allowed_transforms": ["sum_numbers", "missing"]}, catalog)

    assert records[0]["id"] == "sum_numbers"
    assert "{arg}" in records[0]["expression_template"]


def test_contract_transform_operator_catalog_rejects_source_mutation(tmp_path: Path):
    payload = json.loads((ROOT / "config" / "contract_transform_operators.json").read_text(encoding="utf-8"))
    payload["admission_policy"]["automatic_source_mutation_allowed"] = True
    path = tmp_path / "operators.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="automatic source mutation"):
        load_contract_transform_operators(path)
