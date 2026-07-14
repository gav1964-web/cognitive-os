import pytest

from runtime import schema as schema_module


def test_fallback_validator_rejects_additional_properties(monkeypatch) -> None:
    monkeypatch.setattr(schema_module, "jsonschema", None)
    contract = {
        "type": "object",
        "properties": {"value": {"type": "string"}},
        "required": ["value"],
        "additionalProperties": False,
    }

    schema_module.validate_payload({"value": "ok"}, contract, label="payload")
    with pytest.raises(schema_module.SchemaValidationError, match="unexpected properties: extra"):
        schema_module.validate_payload({"value": "ok", "extra": True}, contract, label="payload")
