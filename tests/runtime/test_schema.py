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


def test_fallback_validator_enforces_integer_bounds_and_rejects_bool(monkeypatch) -> None:
    monkeypatch.setattr(schema_module, "jsonschema", None)
    contract = {"type": "integer", "minimum": 1, "maximum": 3}

    schema_module.validate_payload(2, contract, label="payload")
    for value in (True, 0, 4):
        with pytest.raises(schema_module.SchemaValidationError):
            schema_module.validate_payload(value, contract, label="payload")


def test_fallback_validator_recurses_into_array_objects(monkeypatch) -> None:
    monkeypatch.setattr(schema_module, "jsonschema", None)
    contract = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {"name": {"type": "string", "minLength": 2}},
            "required": ["name"],
            "additionalProperties": False,
        },
    }

    with pytest.raises(schema_module.SchemaValidationError):
        schema_module.validate_payload([{"name": "x", "extra": 1}], contract, label="payload")


def test_fallback_validator_fails_closed_on_unsupported_keyword(monkeypatch) -> None:
    monkeypatch.setattr(schema_module, "jsonschema", None)

    with pytest.raises(schema_module.SchemaValidationError, match="unsupported fallback keywords: oneOf"):
        schema_module.validate_payload("x", {"oneOf": [{"type": "string"}]}, label="payload")
